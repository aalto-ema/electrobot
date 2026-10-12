"""Modular collar seats and detachable, identical fork feet; dimensions in mm."""
import json
import hashlib
import math
from dataclasses import asdict
from pathlib import Path


def modules(s):
    positions=s.rack_export_positions()
    result=[]
    for row in range((len(positions)+s.rack_columns-1)//s.rack_columns):
        start=row*s.rack_columns; stop=min(start+s.rack_columns,len(positions))
        for offset in range(start,stop,s.rack_module_slots):
            ids=list(range(offset,min(offset+s.rack_module_slots,stop)))
            supports=sorted(set((0,len(ids)//2,len(ids)-1)))
            result.append({'slots':[i+1 for i in ids],'positions':[positions[i] for i in ids], 'supports':supports})
    return result


def module_frame(m):
    x0,y0,_=m['positions'][0]
    angle=math.atan2(m['positions'][1][1]-y0,m['positions'][1][0]-x0) if len(m['positions'])>1 else 0.0
    c,t=math.cos(angle),math.sin(angle)
    def rounded(v):
        value=round(v,4)
        return 0.0 if value==0 else value
    local=[(rounded(c*(x-x0)+t*(y-y0)),rounded(-t*(x-x0)+c*(y-y0)),0) for x,y,_ in m['positions']]
    return (x0,y0),angle,local


def top_outline(s,positions):
    from shapely.geometry import Point,LineString
    from shapely.ops import unary_union
    radius=s.lattice_dimensions()['outer']
    shapes=[Point(x,y).buffer(radius,quad_segs=24) for x,y,*_ in positions]
    shapes.extend(LineString([a[:2],b[:2]]).buffer(s.rack_rib_width/2,quad_segs=12) for a,b in zip(positions,positions[1:]))
    return unary_union(shapes)


def footprint(s):
    from shapely.ops import unary_union
    from shapely.affinity import rotate,translate
    d=s.lattice_dimensions(); shapes=[]
    for m in modules(s):
        shapes.append(top_outline(s,m['positions']))
        _,angle,_=module_frame(m)
        for i in m['supports']:
            x,y,_=m['positions'][i]
            shapes.append(translate(rotate(foot_outline(s),angle,origin=(0,0),use_radians=True),xoff=x,yoff=y))
    return unary_union(shapes)


def foot_outline(s):
    from shapely.geometry import MultiPoint,LineString
    from shapely.ops import unary_union
    d=s.lattice_dimensions(); offset=d['peg_offset']
    base=MultiPoint([(-offset,0),(offset,0)]).convex_hull.buffer(d['foot_radius'],quad_segs=24)
    return unary_union([base,LineString([(0,0),(0,10)]).buffer(4,quad_segs=24)])


def _cylinder(radius,height,x=0,y=0,z=0):
    import trimesh as tm
    part=tm.creation.cylinder(radius=radius,height=height,sections=64)
    part.apply_translation([x,y,z+height/2]); return part


def _check(mesh):
    from .mesh_utils import connected_solids
    if not mesh.is_watertight or not mesh.is_volume or connected_solids(mesh)!=1:
        raise ValueError('Export part failed closed, connected-solid validation')


def top_mesh(s,m):
    import trimesh as tm
    from shapely.affinity import translate
    d=s.lattice_dimensions(); outline=top_outline(s,m['positions']); origin=outline.bounds[:2]
    outline=translate(outline,xoff=-origin[0],yoff=-origin[1])
    mesh=tm.creation.extrude_polygon(outline,s.rack_deck_thickness,engine='earcut'); cutters=[]
    for i,(x,y,_) in enumerate(m['positions']):
        x-=origin[0]; y-=origin[1]
        cutters.append(_cylinder(d['bore'],s.rack_deck_thickness+.2,x,y,-.1))
        cutters.append(_cylinder(d['seat'],s.rack_seat_depth+.1,x,y,s.rack_deck_thickness-s.rack_seat_depth))
        if i in m['supports']:
            for sign in (-1,1):
                cutters.append(_cylinder((s.rack_peg_diameter+s.rack_peg_clearance)/2,s.rack_peg_length+s.rack_peg_clearance+.1,x+sign*d['peg_offset'],y,-.1))
    mesh=tm.boolean.difference([mesh,*cutters],engine='manifold'); _check(mesh)
    return mesh,origin,outline


def foot_mesh(s):
    import trimesh as tm
    d=s.lattice_dimensions(); offset=d['peg_offset']; radius=d['foot_radius']
    outline=foot_outline(s)
    base=tm.creation.extrude_polygon(outline,s.rack_foot_base,engine='earcut')
    parts=[base]
    for sign in (-1,1):
        parts.append(_cylinder(s.rack_foot_column_diameter/2,d['foot_height']-s.rack_foot_base+.05,sign*offset,0,s.rack_foot_base-.05))
        parts.append(_cylinder(s.rack_peg_diameter/2,s.rack_peg_length+.05,sign*offset,0,d['foot_height']-.05))
    mesh=tm.boolean.union(parts,engine='manifold')
    mesh=tm.boolean.difference([mesh,_cylinder(s.rack_foot_mount_hole/2,s.rack_foot_base+.2,0,10,-.1)],engine='manifold'); _check(mesh)
    mesh.apply_translation([offset+radius,radius,0]); return mesh


def holder_mesh(s):
    import trimesh as tm
    # Printed flange down: rod socket opens upward, avoiding a blind bore roof.
    flange=_cylinder(s.holder_flange_diameter/2,s.holder_flange_thickness)
    body=_cylinder(s.holder_diameter/2,s.holder_height+.05,z=s.holder_flange_thickness-.05)
    mesh=tm.boolean.union([flange,body],engine='manifold'); h=s.holder_height+s.holder_flange_thickness
    cutters=[_cylinder((s.rod_diameter+s.holder_rod_clearance)/2,s.holder_rod_depth+.1,z=h-s.holder_rod_depth),
             _cylinder(s.holder_wire_diameter/2,h+.2,z=-.1),
             _cylinder(s.holder_pad_diameter/2,s.holder_pad_depth+.1,z=-.1)]
    pilot=tm.creation.cylinder(radius=s.holder_set_screw_diameter/2,height=s.holder_diameter/2+1,sections=48)
    pilot.apply_transform(tm.transformations.rotation_matrix(3.141592653589793/2,[0,1,0]))
    pilot.apply_translation([s.holder_diameter/4,0,h-s.holder_rod_depth/2]); cutters.append(pilot)
    mesh=tm.boolean.difference([mesh,*cutters],engine='manifold'); _check(mesh)
    mesh.apply_translation([s.holder_flange_diameter/2,s.holder_flange_diameter/2,0]); return mesh


def export_lattice(s,folder):
    import trimesh as tm
    s.validate(); s.validate_lattice()
    spacing=[message for _,message in s.calibration_issues() if 'Rack slots need' in message]
    if spacing: raise ValueError(spacing[0])
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    d=s.lattice_dimensions(); all_modules=modules(s); parts=[]; instances=[]; signatures={}; total_volume=0
    meshes={'rack_foot.stl':foot_mesh(s),'pickup_holder.stl':holder_mesh(s)}
    for number,m in enumerate(all_modules,1):
        # Shape depends on local coordinates, not its rack location or electrode labels.
        (x0,y0),angle,local=module_frame(m)
        local_module={'positions':local,'supports':m['supports']}
        interface={key:getattr(s,key) for key in ('rod_diameter','we_clearance','holder_diameter','rack_holder_clearance',
                   'rack_seat_depth','rack_deck_thickness','rack_seat_wall','rack_rib_width','rack_peg_diameter','rack_peg_clearance','rack_peg_length','rack_foot_column_diameter')}
        signature=json.dumps((local,m['supports'],interface))
        if signature not in signatures:
            mesh,origin,outline=top_mesh(s,local_module)
            name=f'rack_top_{len(signatures)+1:02d}.stl'; signatures[signature]=name; meshes[name]=mesh
            parts.append({'file':name,'quantity':0,'bounds_mm':mesh.bounds.tolist(),'volume_mm3':float(mesh.volume)})
        name=signatures[signature]; mesh=meshes[name]
        outline=top_outline(s,local); local_origin=outline.bounds[:2]
        c,t=math.cos(angle),math.sin(angle)
        origin=(x0+c*local_origin[0]-t*local_origin[1],y0+t*local_origin[0]+c*local_origin[1])
        next(p for p in parts if p['file']==name)['quantity']+=1
        support_positions=[m['positions'][i][:2] for i in m['supports']]
        instances.append({'module':number,'file':name,'slots':m['slots'],'slot_robot_xyz':m['positions'],
                          'robot_xy_at_stl_origin':list(origin),'assembled_bottom_z_mm':d['foot_height'],
                          'rotation_deg':math.degrees(angle),'slot_local_xy':[[x-local_origin[0],y-local_origin[1]] for x,y,z in local],
                          'foot_centers_robot_xy':support_positions,'foot_orientation':'parallel to this module local X',
                          'geometry_id':hashlib.sha256(signature.encode()).hexdigest()[:12]})
        total_volume+=mesh.volume
    feet=sum(len(m['supports']) for m in all_modules); holders=len(s.rack_export_positions())
    for name,quantity in (('rack_foot.stl',feet),('pickup_holder.stl',holders)):
        mesh=meshes[name]; parts.append({'file':name,'quantity':quantity,'bounds_mm':mesh.bounds.tolist(),'volume_mm3':float(mesh.volume)})
    coupon,_,_=top_mesh(s,{'positions':[(0,0,0)],'supports':[0]})
    meshes['rack_fit_coupon.stl']=coupon
    parts.append({'file':'rack_fit_coupon.stl','quantity':1,'purpose':'optional single-seat fit trial',
                  'bounds_mm':coupon.bounds.tolist(),'volume_mm3':float(coupon.volume)})
    for part in parts:
        x,y,z=[b-a for a,b in zip(*part['bounds_mm'])]
        part['size_mm']=[x,y,z]
        part['geometry_id']=hashlib.sha256(meshes[part['file']].export(file_type='stl')).hexdigest()[:12]
        part['fits_printer_xy']=bool((x<=s.rack_printer_width and y<=s.rack_printer_depth) or (y<=s.rack_printer_width and x<=s.rack_printer_depth))
        if not part['fits_printer_xy']: raise ValueError(f"{part['file']} is {x:.1f} × {y:.1f} mm; reduce slots/module or adjust printer dimensions")
    # Only write after every part validates and fits; existing files aren't silently removed.
    for name,mesh in meshes.items(): mesh.export(folder/name)
    bounds=footprint(s).bounds
    meta={'design':'collar-supported modular lattice','settings':asdict(s),'units':'mm','parts':parts,'modules':instances,
          'slot_robot_xyz':s.rack_export_positions(),'bounds_mm':[[bounds[0],bounds[1],0],[bounds[2],bounds[3],d['seat_height']+s.rack_seat_depth]],
          'seat_height_mm':d['seat_height'],'foot_height_mm':d['foot_height'],'foot_quantity':feet,'holder_quantity':holders,
          'foot_center_local_xy':[d['peg_offset']+d['foot_radius'],d['foot_radius']],
          'foot_mount_hole_local_xy':[d['peg_offset']+d['foot_radius'],d['foot_radius']+10],
          'holder_axis_local_xy':[s.holder_flange_diameter/2,s.holder_flange_diameter/2],
          'rack_solid_volume_mm3':float(total_volume+feet*meshes['rack_foot.stl'].volume),'watertight':True,
          'reuse':'Identical top shapes share a file and quantity. Existing full modules can be reused when slot coordinates, holder/foot dimensions and module size stay unchanged. Feet are identical across this export.',
          'note':'Provisional fits. Print a holder, foot and small top first. Pegs are removable push fits, not locking joints; secure each module to the bench and test wobble/pickup before motion. Metal pad, wire and rod-retention screw are separate; pilot hole is not threaded. Teach rack Z after assembly.'}
    (folder/'rack_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    lines=['# Modular collar-supported rack','',f'Seat height: {d["seat_height"]:.1f} mm. Rod tip clearance: {s.rack_tip_clearance:g} mm.',
           '','Print separate files flat on their Z=0 faces. Inspect the slicer; tall fork feet may need a brim. Holder flange goes on the bed; inspect the contact recess on that face.',
           '','## Print quantities','']
    lines.extend(f'- {p["file"]}: {p["quantity"]} ×; size '+ ' × '.join(f'{v:.1f}' for v in p['size_mm'])+' mm' for p in parts)
    lines.extend(['','## Assembly','',
                  '1. Trial-print one foot, one holder and one small top module. Tune peg and holder clearance to your printer.',
                  '2. Insert rods into the holder sockets and mechanically retain them. Pilot holes require finishing/tapping or a suitable insert; the contact pad and conductor are purchased parts.',
                  '3. Push the paired foot pegs into the blind underside sockets. Seat the top on the column shoulders. Do not rely on an untested push fit for permanent retention.',
                  '4. Rotate each top and its feet by rotation_deg, then position its STL origin at robot_xy_at_stl_origin (manifest). Foot centres are listed in robot XY; paired columns run along module local X. Secure each base using its mounting tab (3.4 mm hole by default, for a separate M3 bolt/washer and suitable bench fixing), or a tested clamp/adhesive fixture. Modules are independent and have no inter-module clips.',
                  '5. Seat the holder bottom in the shallow top recess. Confirm all fingers can reach the exposed body in the pump-off state, neighbors clear, and the active tip hangs free.',
                  '6. Teach actual rack gripping Z and verify every route. Printed seat height is a physical bench dimension, not the robot tool Z.',
                  '',meta['reuse'],'','Only the files listed in this manifest are part of this export; older files in the directory may be obsolete.'])
    (folder/'ASSEMBLY.md').write_text('\n'.join(lines)+'\n')
    return folder/parts[0]['file']
