"""Parametric concept cap. Millimetres. No seal or electrical contacts included."""
from pathlib import Path

def scad(s):
    s.validate()
    inner=s.rim_diameter+s.cap_clearance
    outer=inner+2*s.cap_wall
    bore=s.rod_diameter+s.we_clearance
    return f'''// Electrobot cap concept. Measure actual rim before printing.
// Print flat face down / skirt up; lead-in faces down during printing.
$fn=128;
rim_d={s.rim_diameter}; clearance={s.cap_clearance}; wall={s.cap_wall};
plate={s.cap_thickness}; skirt={s.skirt_depth};
we_d={bore}; mouth={s.funnel_diameter}; re_d={s.re_hole}; ce_d={s.ce_hole};
port_offset={s.port_offset};
inner=rim_d+clearance; outer=inner+2*wall;
difference() {{
 union() {{
  cylinder(h=plate,d=outer);
  translate([0,0,-skirt]) difference() {{
   cylinder(h=skirt+.01,d=outer);
   translate([0,0,-.01]) cylinder(h=skirt+.03,d=inner);
  }}
 }}
 translate([0,0,-.1]) cylinder(h=plate+.2,d=we_d);
 translate([0,0,plate-2]) cylinder(h=2.01,d1=we_d,d2=mouth);
 translate([-port_offset,0,-.1]) cylinder(h=plate+.2,d=re_d);
 translate([port_offset,0,-.1]) cylinder(h=plate+.2,d=ce_d);
 // Open notch for pouring spout and vent; align notch to beaker spout.
 translate([-6,-outer/2-1,-skirt-.1]) cube([12,outer/2-inner/2+3,skirt+plate+.2]);
}}
'''

def export_cap(s,folder):
    s.validate(); folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    (folder/'cell_cap.scad').write_text(scad(s))
    import trimesh
    import numpy as np
    from shapely.geometry import Point, box
    inner=(s.rim_diameter+s.cap_clearance)/2; outer=inner+s.cap_wall
    def disk(radius): return Point(0,0).buffer(radius,quad_segs=64)
    notch=box(-6,-outer-1,6,-inner+2)
    ports=Point(-s.port_offset,0).buffer(s.re_hole/2,quad_segs=64).union(
          Point(s.port_offset,0).buffer(s.ce_hole/2,quad_segs=64))
    plate=disk(outer).difference(ports).difference(notch)
    cap=trimesh.creation.extrude_polygon(plate,s.cap_thickness,engine='earcut')
    skirt=trimesh.creation.extrude_polygon(disk(outer).difference(disk(inner)).difference(notch),s.skirt_depth,engine='earcut')
    skirt.apply_translation([0,0,-s.skirt_depth])
    cap=trimesh.boolean.union([cap,skirt],engine='manifold')
    bore=trimesh.creation.cylinder(radius=(s.rod_diameter+s.we_clearance)/2,height=s.cap_thickness+2,sections=128)
    bore.apply_translation([0,0,s.cap_thickness/2])
    # Frustum: rod bore at lower lead-in, wider mouth at plate top.
    r0=(s.rod_diameter+s.we_clearance)/2; r1=s.funnel_diameter/2
    verts=[]
    for z,r in ((s.cap_thickness-2,r0),(s.cap_thickness+.02,r1)):
        verts.extend([[r*np.cos(a),r*np.sin(a),z] for a in np.linspace(0,2*np.pi,128,endpoint=False)])
    verts.extend([[0,0,s.cap_thickness-2],[0,0,s.cap_thickness+.02]])
    faces=[]
    for i in range(128):
        j=(i+1)%128
        faces.extend([[i,j,128+j],[i,128+j,128+i],[256,j,i],[257,128+i,128+j]])
    funnel=trimesh.Trimesh(vertices=verts,faces=faces,process=True)
    mesh=trimesh.boolean.difference([cap,bore,funnel],engine='manifold')
    if not mesh.is_watertight or not mesh.is_volume:
        raise ValueError('Cap mesh failed closed-solid validation')
    mesh.export(folder/'cell_cap.stl')
    return folder/'cell_cap.stl'

if __name__=='__main__':
    from .config import Settings
    print(export_cap(Settings(),'cad'))
