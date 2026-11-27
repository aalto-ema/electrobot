"""Bounded, read-only controller sampling and shared transfer graph routing.

Accepted samples are not obstacle clearance or a continuous kinematic proof.
"""
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib
import heapq
import json
import math
from .robot_checks import segment_samples

FORMAT='electrobot-transfer-plan-v1'
MAX_QUERIES=16000


def signature(s):
    keys=('safe_z','tool_r','reachability_step',
          'position_tolerance','controller_preflight','beaker_diameter','rinse_beaker_diameter',
          'shoulder_diameter','rod_diameter','we_clearance','rinse_x','rinse_y','rinse_z')
    values={k:v for k,v in asdict(s).items() if k in keys or k.startswith(('rack_','holder_','cell_','workspace_')) and k!='workspace_map'}
    return hashlib.sha256(json.dumps(values,sort_keys=True,allow_nan=False).encode()).hexdigest()


def validate_plan(plan):
    if not plan: return
    if not isinstance(plan,dict) or plan.get('format')!=FORMAT: raise ValueError('Invalid transfer plan format')
    if type(plan.get('slot_count')) is not int or not 1<=plan['slot_count']<=100: raise ValueError('Invalid planned rack slot count')
    initial=plan.get('initial_pose')
    if not isinstance(initial,list) or len(initial)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in initial):
        raise ValueError('Invalid transfer plan initial pose')
    nodes=plan.get('nodes'); edges=plan.get('edges')
    if not isinstance(nodes,list) or not 1<=len(nodes)<=1500: raise ValueError('Invalid transfer plan nodes')
    for p in nodes:
        if not isinstance(p,list) or len(p)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p):
            raise ValueError('Transfer plan poses must contain finite XYZ/R')
        if max(abs(v) for v in p[:3])>400 or abs(p[3])>90: raise ValueError('Transfer plan pose exceeds planner search range')
        if p[2:]!=nodes[0][2:]: raise ValueError('Transfer waypoints must share a fixed height and rotation')
    if not isinstance(edges,list) or len(edges)>6000: raise ValueError('Invalid transfer plan edges')
    shortcuts=plan.get('shortcut_edges',[])
    if not isinstance(shortcuts,list) or len(shortcuts)>6000: raise ValueError('Invalid simplified transfer edges')
    for edge in edges+shortcuts:
        if not isinstance(edge,list) or len(edge)!=2 or any(type(i) is not int or not 0<=i<len(nodes) for i in edge) or edge[0]==edge[1]:
            raise ValueError('Invalid transfer plan edge')
    if not isinstance(plan.get('signature'),str) or len(plan['signature'])!=64: raise ValueError('Missing transfer plan settings signature')


def adjacency(nodes,edges):
    graph=[[] for _ in nodes]
    for a,b in edges:
        weight=math.dist(nodes[a][:2],nodes[b][:2])
        graph[a].append((b,weight)); graph[b].append((a,weight))
    return graph


def shortest(graph,start,end):
    distances={start:0}; parents={}; todo=[(0,start)]
    while todo:
        cost,i=heapq.heappop(todo)
        if cost!=distances[i]: continue
        if i==end:
            path=[i]
            while i!=start: i=parents[i]; path.append(i)
            return list(reversed(path))
        for j,w in graph[i]:
            if cost+w<distances.get(j,float('inf')):
                distances[j]=cost+w; parents[j]=i; heapq.heappush(todo,(cost+w,j))
    raise ValueError('No connected controller-sampled transfer route')


def transfer_waypoints(s,start,target):
    """Shared by preview/preflight and execution; never silently fall back."""
    plan=s.transfer_plan
    if not plan: return [(*target[:2],s.safe_z,s.tool_r)]
    validate_plan(plan)
    if s.first_electrode+s.electrodes-1>plan['slot_count']:
        raise ValueError('Selected electrodes extend beyond the planned rack. Find a working layout again.')
    if plan['signature']!=signature(s): raise ValueError('Layout or route settings changed. Find a working layout again, or explicitly remove the transfer plan.')
    if math.dist(start[:2],target[:2])<1e-8: return [(*target[:2],s.safe_z,s.tool_r)]
    nodes=plan['nodes']
    def locate(p):
        i=min(range(len(nodes)),key=lambda i:math.dist(nodes[i][:2],p[:2]))
        if math.dist(nodes[i][:2],p[:2])>s.position_tolerance+1e-4:
            raise ValueError('Robot or station is outside the saved transfer graph. Find a working layout again from the current pose.')
        return i
    a,b=locate(start),locate(target)
    path=[tuple(nodes[i]) for i in shortest(adjacency(nodes,plan['edges']+(plan.get('shortcut_edges',[]) if s.route_simplification else [])),a,b)]
    # Include the source node: a reported pose can differ slightly from its target.
    if math.dist(path[-1][:2],target[:2])>1e-8: path.append((*target[:2],s.safe_z,s.tool_r))
    # A straight MOVL spans consecutive graph edges on the same line.
    # Keep the first and last node, every turn, and every reversal.
    waypoints=[]
    for point in path:
        if len(waypoints)>=2:
            a,b=waypoints[-2:]
            dx,dy=point[0]-a[0],point[1]-a[1]
            bx,by=b[0]-a[0],b[1]-a[1]
            length=math.hypot(dx,dy)
            projection=bx*dx+by*dy
            if (length and a[2:]==b[2:]==point[2:] and 0<projection<length*length
                    and abs(dx*by-dy*bx)<=1e-8*length):
                waypoints.pop()
        waypoints.append(point)
    return waypoints


def simplify_transfers(settings,initial,segment,check=lambda:None):
    """Greedy farthest-accepted shortcuts for this batch; retain the base graph."""
    from copy import deepcopy
    s=replace(settings,transfer_plan=deepcopy(settings.transfer_plan),route_simplification=False)
    if not s.transfer_plan: return s.transfer_plan
    s.transfer_plan.pop('shortcut_edges',None)
    route=s.planned_route(initial)  # Also rejects stale/out-of-coverage plans.
    nodes=s.transfer_plan['nodes']; lookup={tuple(p):i for i,p in enumerate(nodes)}
    groups=[]; group=[]
    for label,pose in route:
        if ' transfer ' in label: group.append(tuple(pose))
        elif group: groups.append(group); group=[]
    if group: groups.append(group)
    edges=set(); tried={}
    for points in groups:
        check(); indices=[]
        for p in points:
            if p in lookup and (not indices or indices[-1]!=lookup[p]): indices.append(lookup[p])
        start=0
        while start<len(indices)-1:
            check(); chosen=start+1
            for end in range(len(indices)-1,start+1,-1):
                key=tuple(sorted((indices[start],indices[end])))
                if key not in tried: tried[key]=segment(nodes[indices[start]],nodes[indices[end]])
                if tried[key]:
                    edges.add(key); chosen=end; break
            start=chosen
    s.transfer_plan['shortcut_edges']=[list(e) for e in sorted(edges)]
    s.transfer_plan['simplification']={'source':'controller segment queries','checked_candidates':len(tried),'shortcuts':len(edges)}
    validate_plan(s.transfer_plan)
    return s.transfer_plan


class LayoutPlanner:
    def __init__(self,settings,limited,check=lambda:None,progress=lambda message:None,max_queries=MAX_QUERIES):
        self.s=replace(settings,transfer_plan={}); self.limited=limited
        self.check=check; self.progress=progress; self.max_queries=max_queries
        self.cache={}; self.queries=0; self.rejected=None

    def accepted(self,pose):
        self.check(); p=tuple(pose)
        try: self.s.validate_pose(p)
        except ValueError: self.rejected=p; return False
        if p not in self.cache:
            if self.queries>=self.max_queries:
                raise ValueError('Planner query budget reached; no layout applied. This search could not finish within its query limit.')
            limited=self.limited(p)
            if type(limited) is not bool: raise ValueError('Controller limit query did not return a boolean; planning aborted')
            self.cache[p]=not limited; self.queries+=1
            if self.queries%100==0: self.progress(f'{self.queries} controller queries · no motion · fixed travel Z {self.s.safe_z:g} mm')
        if not self.cache[p]: self.rejected=p
        return self.cache[p]

    def segment(self,a,b):
        return all(self.accepted(p) for p in segment_samples(a,b,self.s.reachability_step))

    def required(self,a,b,label):
        if not self.segment(a,b):
            raise ValueError(f'{label} is rejected at XYZ/R {tuple(round(v,2) for v in self.rejected)}. '
                             'Teach a different position or clearance height; the planner will not lower your taught height.')

    def find(self,initial,count=32,spacing=36):
        s=self.s
        if type(count) is not int or not 1<=count<=100: raise ValueError('Choose 1–100 electrodes')
        if not math.isfinite(spacing) or not 10<=spacing<=100: raise ValueError('Choose electrode spacing between 10 and 100 mm')
        s.validate()
        minimum=s.lattice_dimensions()['separation'] if s.rack_design=='lattice' else max(s.shoulder_diameter+4,s.rod_diameter+s.rack_socket_clearance+2*s.rack_socket_wall+1)
        spacing=max(spacing,minimum+.1)
        initial=tuple(initial)
        if len(initial)!=4 or not all(math.isfinite(v) and abs(v)<=400 for v in initial): raise ValueError('Invalid initial robot pose')
        top=lambda x,y:(x,y,s.safe_z,s.tool_r)
        cell=(s.cell_x,s.cell_y,s.cell_z,s.tool_r); rinse=(s.rinse_x,s.rinse_y,s.rinse_z,s.tool_r)
        self.progress('Checking taught cell, rinse and initial vertical paths…')
        for label,p in (('Cell seating/lift',cell),('Rinse dipping/lift',rinse),('Current robot lift',initial)):
            self.required(p,top(*p[:2]),label)
        radii=list(range(120,341,20)); angles=list(range(-90,91,5))
        nodes=[]; edges=[]; grid={}
        self.progress('Sampling transfer height across the front of the robot…')
        for ri,r in enumerate(radii):
            self.check()
            for ai,a in enumerate(angles):
                p=top(round(r*math.cos(math.radians(a)),2),round(r*math.sin(math.radians(a)),2))
                if self.accepted(p): grid[ri,ai]=len(nodes); nodes.append(p)
        self.progress('Checking every transfer segment between neighbouring samples…')
        for (ri,ai),i in grid.items():
            for key in ((ri+1,ai),(ri,ai+1)):
                j=grid.get(key)
                if j is not None and self.segment(nodes[i],nodes[j]): edges.append([i,j])
        anchors=[]
        for label,p in (('Current robot',initial),('Cell',cell),('Rinse',rinse)):
            target=top(*p[:2]); exact=next((i for i,n in enumerate(nodes) if n==target),None)
            if exact is not None: anchors.append(exact); continue
            # Fixed number of nearby connections; never invent an unqueried edge.
            near=sorted(range(len(nodes)),key=lambda i:math.dist(nodes[i][:2],target[:2]))[:24]
            links=[i for i in near if self.segment(target,nodes[i])]
            if not links: raise ValueError(f'{label} has an accepted vertical path but no connection to the sampled transfer network. Teach it nearer the front workspace, or revise the clearance height.')
            index=len(nodes); nodes.append(target); anchors.append(index)
            edges.extend([index,i] for i in links)
        graph=adjacency(nodes,edges)
        for endpoint in anchors[1:]:
            try: shortest(graph,anchors[0],endpoint)
            except ValueError as exc: raise ValueError('Cell, rinse and current robot lie in disconnected sampled regions at the taught clearance height. Change station placement or teach another clearance height.') from exc
        connected={anchors[0]}; todo=list(connected)
        while todo:
            for j,_ in graph[todo.pop()]:
                if j not in connected: connected.add(j); todo.append(j)
        self.progress('Checking rack pickup/lift paths and fixture footprints…')
        usable=set()
        for key,i in grid.items():
            if i not in connected: continue
            p=nodes[i]
            if any(math.dist(p[:2],c[:2])<diameter/2+max(s.shoulder_diameter,s.holder_flange_diameter)/2+s.rack_gripper_gap
                   for c,diameter in ((cell,s.beaker_diameter),(rinse,s.rinse_beaker_diameter))): continue
            if self.segment((*p[:2],s.rack_z,s.tool_r),p): usable.add(key)
        # Regular radial racks only: shared rack_pose remains the sole slot mapping.
        row_stride=max(1,math.ceil(spacing/20)); candidates=[]
        for ri,r in enumerate(radii):
            self.check()
            angle_stride=max(1,math.ceil(math.degrees(2*math.asin(min(1,spacing/(2*r))))/5))
            for ai,a in enumerate(angles):
                for rows in range(1,5):
                    if ri+(rows-1)*row_stride>=len(radii): break
                    columns=0
                    for col in range(20):
                        aj=ai+col*angle_stride
                        if aj>=len(angles) or any((ri+row*row_stride,aj) not in usable for row in range(rows)): break
                        columns+=1
                        capacity=columns*rows
                        if capacity>100: break
                        candidates.append((capacity,ri,ai,rows,columns,angle_stride))
        if not candidates: raise ValueError('No rack slots fit the sampled reach, taught pickup height and station footprints. No settings changed. Revisit pickup/clearance heights or cell/rinse placement.')
        capacity=max(c[0] for c in candidates)
        desired=min(count,capacity)
        # Prefer few spare slots, then fewer radial rows and proximity to existing rack.
        candidates=[c for c in candidates if c[0]>=desired]
        choice=min(candidates,key=lambda c:(c[0]-desired,c[3],abs(radii[c[1]]-s.rack_radius),abs(angles[c[2]]+(c[4]-1)*c[5]*2.5)))
        _,ri,ai,rows,columns,stride=choice
        proposed=replace(s,first_electrode=1,electrodes=desired,rack_layout='radial',rack_columns=columns,
                         rack_radius=float(radii[ri]),rack_start_angle=float(angles[ai]),rack_angle_step=float(stride*5),
                         rack_pitch=float(row_stride*20),calibrated=False,fixture_verified=False,controller_preflight=True)
        # rack_pose uses full-precision trig, so verify exact final coordinates and attach
        # them explicitly rather than relying on rounded search-node positions.
        for pose in proposed.rack_export_positions():
            p=top(*pose[:2]); self.required((*pose,s.tool_r),p,'Final rack pickup/lift')
            nearest=min(connected,key=lambda i:math.dist(nodes[i][:2],p[:2]))
            self.required(nodes[nearest],p,'Final rack connection')
            if p!=nodes[nearest]:
                index=len(nodes); nodes.append(p); edges.append([nearest,index])
        proposed.validate()
        issues=proposed.calibration_issues()
        if issues: raise ValueError('; '.join(dict.fromkeys(m for _,m in issues)))
        plan=dict(format=FORMAT,signature=signature(proposed),nodes=[list(p) for p in nodes],edges=edges,
                  created_utc=datetime.now(timezone.utc).isoformat(),source='DobotLink.CheckPoseLimit',queries=self.queries,
                  search='Radial grid: r 120–340 mm / 20 mm; angle −90…90° / 5°; up to four rack rows',
                  initial_pose=list(initial),requested=count,capacity=capacity,spacing=spacing,slot_count=len(proposed.rack_export_positions()))
        validate_plan(plan); proposed.transfer_plan=plan
        # Resolve every actual sequence transfer, including initial entry, before offering Apply.
        if proposed.route_simplification:
            self.progress('Checking shortcut segments to simplify transfer routes…')
            proposed.transfer_plan=simplify_transfers(proposed,initial,self.segment,self.check)
            plan=proposed.transfer_plan
        route=proposed.planned_route(initial)
        for (_,a),(_,b) in zip(route,route[1:]): self.required(a,b,'Final experiment route')
        plan['queries']=self.queries
        self.progress(f'Found {desired}/{count} electrodes; best sampled regular-rack capacity {capacity}. {self.queries} controller queries.')
        return proposed
