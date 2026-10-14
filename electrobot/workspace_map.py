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
