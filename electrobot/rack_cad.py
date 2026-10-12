"""Rod rack CAD using the exact same XY slot locations as robot execution."""
import json
from pathlib import Path
from dataclasses import asdict


def rack_geometry(s):
    from shapely.geometry import Point,MultiPoint
    positions=s.rack_export_positions()
    bore=(s.rod_diameter+s.rack_socket_clearance)/2
    outer=bore+s.rack_socket_wall
    xy=[p[:2] for p in positions]
    # Convex envelope gives a stable connected base, including for one row.
    base=MultiPoint(xy).convex_hull.buffer(outer+s.rack_margin,quad_segs=24)
    return positions,base,bore,outer


def export_rack(s,folder):
    s.validate()
    issues=[m for keys,m in s.calibration_issues() if 'Rack slots need' in m]
    if issues: raise ValueError(issues[0])
    import trimesh as tm
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    positions,base,bore,outer=rack_geometry(s)
    origin=base.bounds[:2]
    from shapely.affinity import translate
    base=translate(base,xoff=-origin[0],yoff=-origin[1])
    mesh=tm.creation.extrude_polygon(base,s.rack_base_thickness,engine='earcut')
    posts=[]; cutters=[]
    for x,y,_ in positions:
        x-=origin[0]; y-=origin[1]
        post=tm.creation.cylinder(radius=outer,height=s.rack_post_height+.05,sections=64)
        post.apply_translation([x,y,s.rack_base_thickness+s.rack_post_height/2-.025]); posts.append(post)
        cut=tm.creation.cylinder(radius=bore,height=s.rack_socket_depth+.1,sections=64)
        cut.apply_translation([x,y,s.rack_base_thickness+s.rack_post_height-s.rack_socket_depth/2+.05]); cutters.append(cut)
    mesh=tm.boolean.union([mesh,*posts],engine='manifold')
    mesh=tm.boolean.difference([mesh,*cutters],engine='manifold')
    # Reuse connected-component check without scipy.
    from .mesh_utils import connected_solids
    if not mesh.is_watertight or not mesh.is_volume or connected_solids(mesh)!=1:
        raise ValueError('Rack failed closed, connected-solid validation')
    mesh.export(folder/'electrode_rack.stl')
    coords=[[round(x-origin[0],4),round(y-origin[1],4)] for x,y,_ in positions]
    source='// Millimetres. Blind rod sockets. Robot XY origin recorded in JSON.\n$fn=64;\n'
    source+=f'base_h={s.rack_base_thickness}; post_h={s.rack_post_height}; depth={s.rack_socket_depth}; bore={2*bore}; outer={2*outer};\n'
    source+='slots='+json.dumps(coords)+';\n'
    # Same convex buffered profile as STL, sampled as a polygon.
    source+='outline='+json.dumps([[round(x,5),round(y,5)] for x,y in base.exterior.coords[:-1]])+';\n'
    source+='difference(){ union(){linear_extrude(base_h) polygon(outline); for(p=slots) translate([p[0],p[1],base_h-.05]) cylinder(h=post_h+.05,d=outer);} for(p=slots) translate([p[0],p[1],base_h+post_h-depth]) cylinder(h=depth+.1,d=bore);}\n'
    (folder/'electrode_rack.scad').write_text(source)
    meta={'settings':asdict(s),'units':'mm','robot_xy_at_stl_origin':list(origin),
          'slot_robot_xyz':positions,'slot_local_xy':coords,'bounds_mm':mesh.bounds.tolist(),
          'watertight':bool(mesh.is_watertight),'connected_solids':1,
          'note':'Print base down. Blind sockets may touch active tips; use dummy rods first. Rack gripping Z must be taught after assembly; it does not determine printed height. No flag-electrode insert yet.'}
    (folder/'rack_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return folder/'electrode_rack.stl'
