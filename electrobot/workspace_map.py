"""Non-moving workspace query plans. Accepted points are not collision clearance."""
import math

MAX_POINTS=5000


def axis_values(low,high,step):
    if not all(math.isfinite(v) for v in (low,high,step)) or low>high or step<=0:
        raise ValueError('Each scan needs finite minimum ≤ maximum and a positive step')
    if (high-low)/step>MAX_POINTS: raise ValueError('Scan axis is too dense')
    values=[round(low+i*step,6) for i in range(math.floor((high-low)/step)+1)]
    if not math.isclose(values[-1],high,abs_tol=1e-6): values.append(high)
    return values


def scan_axes(spec):
    axes=[axis_values(spec[k+'_min'],spec[k+'_max'],spec[k+'_step']) for k in 'xyz']
    if not math.isfinite(spec['r']) or not -90<=spec['r']<=90: raise ValueError('Scan R must be between −90° and +90°')
    if any(abs(v)>400 for axis in axes for v in axis): raise ValueError('Scan coordinates must be within ±400 mm')
    if math.prod(len(axis) for axis in axes)>MAX_POINTS:
        raise ValueError(f'Scan exceeds {MAX_POINTS} queries. Use a coarser grid, fewer Z heights or a smaller XY area.')
    return axes


def scan_points(spec):
    xs,ys,zs=scan_axes(spec)
    return [(x,y,z,spec['r']) for y in ys for x in xs for z in zs]


def validate_saved_map(data):
    if data.get('format')!='electrobot-controller-workspace-v1': raise ValueError('Not an Electrobot workspace map')
    if data.get('source')!='DobotLink.CheckPoseLimit': raise ValueError('Unsupported workspace map source')
    xs,ys,zs=scan_axes(data['spec']); allowed=set(scan_points(data['spec']))
    points=data.get('points',[])
    if not isinstance(points,list) or len(points)>MAX_POINTS: raise ValueError('Invalid workspace point count')
    seen=set()
    for p in points:
        if not isinstance(p,(list,tuple)) or len(p)!=6 or type(p[4]) is not bool or type(p[5]) is not bool:
            raise ValueError('Invalid map point (XYZR, controller accepted, configured bounds)')
        if tuple(p[:4]) not in allowed or tuple(p[:4]) in seen: raise ValueError('Point outside scan grid or duplicated')
        seen.add(tuple(p[:4]))
    if data.get('complete') and len(seen)!=len(allowed): raise ValueError('Complete map has missing samples')
    return data


class Envelope:
    """Planning support from surrounding samples, never continuous reach proof."""
    def __init__(self,data):
        self.data=validate_saved_map(data)
        self.xs,self.ys,self.zs=scan_axes(data['spec'])
        self.points={tuple(p[:3]):p[4] for p in data['points']}

    @staticmethod
    def bracket(axis,value):
        if value<axis[0] or value>axis[-1]: return []
        if value in axis: return [value]
        for a,b in zip(axis,axis[1:]):
            if a<value<b: return [a,b]
        return []

    def status(self,x,y,low,high,r):
        if not math.isclose(r,self.data['spec']['r'],abs_tol=.001): return None
        xs,ys=self.bracket(self.xs,x),self.bracket(self.ys,y)
        a,b=self.bracket(self.zs,low),self.bracket(self.zs,high)
        if not xs or not ys or not a or not b or low>high: return None
        zs=[z for z in self.zs if min(a)<=z<=max(b)]
        values=[self.points.get((xx,yy,z)) for xx in xs for yy in ys for z in zs]
        if any(v is False for v in values): return False
        return True if all(v is True for v in values) else None

    def rectangle(self,low,high,r):
        """Largest area grid rectangle whose cells have accepted corner columns."""
        heights=[0]*(len(self.xs)-1); best=None; area=0
        for j in range(len(self.ys)-1):
            for i in range(len(heights)):
                good=all(self.status(x,y,low,high,r) is True
                         for x in self.xs[i:i+2] for y in self.ys[j:j+2])
                heights[i]=heights[i]+1 if good else 0
            stack=[]
            for i,h in enumerate(heights+[0]):
                start=i
                while stack and stack[-1][1]>h:
                    left,height=stack.pop(); start=left
                    bounds=(self.xs[left],self.xs[i],self.ys[j-height+1],self.ys[j+1])
                    size=(bounds[1]-bounds[0])*(bounds[3]-bounds[2])
                    if size>area: area=size; best=bounds
                if not stack or stack[-1][1]<h: stack.append((start,h))
        if best is None: raise ValueError('No accepted XY rectangle covers this Z range and R. Scan more heights/area or refine the grid.')
        return best


def fit_rack(settings,data):
    """Preview a nearest sampled anchor; preserve layout, slot mapping and spacing."""
    from dataclasses import replace
    envelope=Envelope(data); candidates=[]
    low=min(settings.rack_z,settings.cell_z,settings.rinse_z); high=settings.safe_z
    original=settings.rack_pose(1)
    for y in envelope.ys:
        for x in envelope.xs:
            if settings.rack_layout=='radial':
                radius=math.hypot(x,y)
                angle=math.degrees(math.atan2(y,x))
                candidate=replace(settings,rack_radius=radius,rack_start_angle=angle)
            else: candidate=replace(settings,rack_x=x,rack_y=y)
            good=True
            for pose in candidate.rack_export_positions():
                if envelope.status(*pose[:2],low,high,candidate.tool_r) is not True:
                    good=False; break
                try:
                    candidate.validate_pose(pose)
                    candidate.validate_pose((*pose[:2],high,candidate.tool_r))
                except ValueError: good=False; break
            if good and any(message.startswith('Rack slots need') for _,message in candidate.calibration_issues()): good=False
            if good: candidates.append((math.dist(original[:2],(x,y)),candidate))
    if not candidates: raise ValueError('No rack placement fits the supported map and configured bounds. Reduce rack size, adjust spacing or scan a larger area.')
    return min(candidates,key=lambda item:item[0])[1]
