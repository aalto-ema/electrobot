"""Experimental split holder for the selected 6 mm electrode; millimetres."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import trimesh as tm
from .mesh_utils import connected_solids


def box(size,center):
    mesh=tm.creation.box(extents=size); mesh.apply_translation(center); return mesh


def cylinder(d,h,z,axis='z',x=0,y=0):
    mesh=tm.creation.cylinder(radius=d/2,height=h,sections=96)
    if axis=='y': mesh.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    mesh.apply_translation([x,y,z]); return mesh


def holder_halves(d):
    numeric=[v for v in d.values() if isinstance(v,(int,float))]
    if any(not math.isfinite(v) or v<=0 for v in numeric): raise ValueError('Dimensions must be finite and positive')
    h=d['total_height']; pilot=d['pilot_height']; ft=d['flange_thickness']; bd=d['body_diameter']
    bore=d['electrode_body_diameter']+d['bore_clearance']
    if not bore+4<d['pilot_diameter']<=bd: raise ValueError('Invalid pilot diameter')
    if d['electrode_body_length_estimate']<=h: raise ValueError('Electrode must extend below holder')
    if len(d['printer_bed'])!=2 or any(not math.isfinite(v) or v<=0 for v in d['printer_bed']): raise ValueError('Invalid printer bed')
    if not bore+5<bd<d['flange_diameter']: raise ValueError('Insufficient bore wall or flange')
    if not 0<d['split_gap']<bore/4: raise ValueError('Invalid clamp gap')
    if not pilot+ft<d['contact_z']<d['contact_z']+d['contact_width']<d['bolt_z']-d['bolt_diameter']/2<h-2:
        raise ValueError('Pilot, flange, contact and bolt heights overlap')
    if not bore/2+d['bolt_diameter']/2+.5<d['bolt_x']<bd/2-d['bolt_diameter']/2-.5:
        raise ValueError('Bolt holes need clearance from rod and outer wall')
    flange=tm.creation.revolve(np.array([[0,pilot],[bd/2,pilot],
        [d['flange_diameter']/2,pilot+ft/2],[bd/2,pilot+ft],[0,pilot+ft]]),sections=96)
    solid=tm.boolean.union([cylinder(d['pilot_diameter'],pilot+.05,(pilot+.05)/2),
        cylinder(bd,h-pilot,h/2+pilot/2),flange],engine='manifold')
    tools=[cylinder(bore,h+2,h/2),box([bd*3,d['split_gap'],h+2],[0,0,h/2])]
    # Recessed foil band; the purchased ring bridges the split after clamping.
    outer=cylinder(bd+2,d['contact_width'],d['contact_z']+d['contact_width']/2)
    inner=cylinder(bd-2*d['contact_recess'],d['contact_width']+2,d['contact_z']+d['contact_width']/2)
    tools.append(tm.boolean.difference([outer,inner],engine='manifold'))
    channel_h=h-d['contact_z']
    tools.append(cylinder(2*d['wire_channel_radius'],channel_h+1,d['contact_z']+channel_h/2+.5,
                          y=-bd/2+.3))
    for sign in (-1,1):
        tools.append(cylinder(d['bolt_diameter'],bd+4,d['bolt_z'],axis='y',x=sign*d['bolt_x']))
        for side in (-1,1):
            # Recessed flats under separate washers/nuts; no printed threads.
            tools.append(box([8,bd,6],[sign*d['bolt_x'],side*(d['bolt_flat_y']+bd/2),d['bolt_z']]))
        nut=tm.creation.cylinder(radius=d['nut_across_flats']/math.sqrt(3),height=d['nut_depth']+.2,sections=6)
        nut.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
        nut.apply_translation([sign*d['bolt_x'],d['bolt_flat_y']-d['nut_depth']/2+.05,d['bolt_z']])
        tools.append(nut)
    cut=tm.boolean.difference([solid,*tools],engine='manifold')
    halves=[]
    for side in (-1,1):
        half=tm.boolean.intersection([cut,box([bd*3,bd*2,h+4],[0,side*bd,h/2])],engine='manifold')
        if not half.is_watertight or not half.is_volume or connected_solids(half)!=1:
            raise ValueError('Holder half is not a closed connected solid')
        halves.append(half)
    return halves


def export_holder(dimensions,folder):
    d=dimensions; folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    halves=holder_halves(d); parts=[]; plate=[]
    cursor=5.
    for label,mesh in zip(('rear','front'),halves):
        # Flat split face down, electrode axis along print Y. Open half-bore up.
        print_mesh=mesh.copy()
        print_mesh.apply_transform(tm.transformations.rotation_matrix(-math.pi/2 if label=='rear' else math.pi/2,[1,0,0]))
        origin_shift=-print_mesh.bounds[0]
        print_mesh.apply_translation(origin_shift)
        filename=f'holder_{label}.stl'; print_mesh.export(folder/filename)
        placed=print_mesh.copy(); placed.apply_translation([cursor,5,0]); plate.append(placed)
        parts.append(dict(file=filename,quantity=1,size_mm=print_mesh.extents.tolist(),
                          print_bounds_mm=print_mesh.bounds.tolist(),assembly_bounds_mm=mesh.bounds.tolist(),volume_mm3=float(mesh.volume),watertight=bool(mesh.is_watertight),connected_solids=connected_solids(mesh),
                          plate_translation_mm=[cursor,5,0],
                          print_rotation_x_deg=-90 if label=='rear' else 90,
                          print_origin_translation_mm=origin_shift.tolist()))
        cursor+=print_mesh.extents[0]+4
    kit=tm.util.concatenate(plate)
    if any(kit.bounds[1,i]>d['printer_bed'][i]-5 for i in (0,1)): raise ValueError('Parts exceed configured print bed')
    kit.export(folder/'holder_pair_print_plate.stl')
    # A short split bore coupon uses the same tolerances and closure gap.
    coupon=cylinder(d['body_diameter'],4,2)
    coupon=tm.boolean.difference([coupon,cylinder(d['electrode_body_diameter']+d['bore_clearance'],6,2),
                                 box([d['body_diameter']*2,d['split_gap'],6],[0,0,2])],engine='manifold')
    coupon.apply_translation(-coupon.bounds[0]); coupon.export(folder/'bore_fit_coupon.stl')
    manifest=dict(design='6 mm electrode split carrier v1',units='mm',dimensions=d,parts=parts,
        geometry_id=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:16],
        assembly_frame='Z=0 pilot bottom; +Z toward terminal; split plane Y=0; electrode axis X=Y=0',
        electrode_body_top_z_mm=d['total_height'],estimated_tip_z_mm=d['total_height']-d['electrode_body_length_estimate'],
        estimated_hanging_below_deck_mm=d['electrode_body_length_estimate']-d['total_height']+d['pilot_height'],
        contact_center_z_mm=d['contact_z']+d['contact_width']/2,
        minimum_contact_retraction_geometry_mm=(d['flange_diameter']-(d['body_diameter']-2*d['contact_recess']))/2,
        rack_interface=dict(pilot_diameter_mm=d['pilot_diameter'],pilot_depth_mm=d['pilot_height'],flange_diameter_mm=d['flange_diameter']),
        print_plate_bounds_mm=kit.bounds.tolist(),print_plate_solids=connected_solids(kit),
        fit_coupon=dict(file='bore_fit_coupon.stl',quantity=1,solids=connected_solids(coupon),size_mm=coupon.extents.tolist()),
        purchased=['2 M3 x 12 bolts (provisional length), 2 M3 nuts, 2 compact M3 washers (OD <=6 mm) under bolt heads',
                   '3 mm wide thin copper foil strip; tinned copper tab and insulated wire',
                   'Removable socket or screw-clamp contact matched to measured electrode terminal',
                   'Separate compliant cell-mounted contact and its insulating mount; not supplied'],
        warning='Prototype only. No demonstrated electrode/gripper fit, grip retention, chemical compatibility or electrical qualification.')
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
