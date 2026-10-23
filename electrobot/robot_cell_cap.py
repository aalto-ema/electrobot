"""Photo-informed modular cell-cap prototype; all coordinates and STL units mm."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import trimesh as tm

from .electrode_holder import box, cylinder
from .fixed_contact_cad import annulus, union, subtract, parts as contact_parts, interface as contact_interface
from .mesh_utils import connected_solids

REVISION = 'robot-cell-cap-v1'


def helical_thread(major, pitch, depth, length, lead=0):
    """Closed right-hand, truncated-profile trial thread, tip at +Z.

    This is a fit-test geometry, not a claim of compliance with an OEM or ISO
    thread form. A real helix is used, rather than stacked circumferential rings.
    """
    if not 0 < depth < major/4 or pitch <= 0 or length <= pitch or not 0 <= lead < length:
        raise ValueError('Invalid trial thread dimensions')
    root = major/2-depth
    turns = length/pitch+2
    count = math.ceil(turns*96)
    angles = np.linspace(-2*math.pi, 2*math.pi*(length/pitch+1), count+1)
    profile = [(root-.03, -.4*pitch), (major/2, -.12*pitch),
               (major/2, .12*pitch), (root-.03, .4*pitch)]
    vertices = [[r*math.cos(a), r*math.sin(a), pitch*a/(2*math.pi)+z]
                for a in angles for r, z in profile]
    faces = []
    for i in range(count):
        for k in range(4):
            j = (k+1)%4; a = i*4+k; b = i*4+j; c = (i+1)*4+j; e = (i+1)*4+k
            faces.extend([[a,b,c],[a,c,e]])
    faces.extend([[0,2,1],[0,3,2],[count*4,count*4+1,count*4+2],[count*4,count*4+2,count*4+3]])
    ridge = tm.Trimesh(vertices=vertices, faces=faces, process=True)
    ridge.fix_normals(multibody=False)
    thread = union([cylinder(2*root, length, length/2), ridge])
    clip = cylinder(major+2, length, length/2)
    if lead:
        clip = tm.creation.revolve(np.array([[0,0],[major/2,0],[major/2,length-lead],
                       [max(root,major/2-.7),length],[0,length]]), sections=96)
    return tm.boolean.intersection([thread,clip], engine='manifold')


def at(mesh, xyz):
    mesh = mesh.copy(); mesh.apply_translation(xyz); return mesh


def stack_interfaces(d, contact):
    fit = contact_interface(contact)
    seat = d['deck_thickness']+d['we_socket_rise']
    insert_z = seat-(contact['insert_height']-contact['insert_flange_height'])
    holder_z = insert_z+fit['holder_bottom_z_mm']
    return dict(socket_seat_z_mm=seat, insert_origin_z_mm=insert_z,
                cover_bottom_z_mm=insert_z-contact['cover_thickness'],
                cover_to_deck_gap_mm=insert_z-contact['cover_thickness']-d['deck_thickness'],
                holder_origin_z_mm=holder_z,
                electrode_body_top_z_mm=holder_z+contact['holder_height'],
                estimated_we_tip_z_mm=holder_z+contact['holder_height']-contact['electrode_length_estimate'],
                glass_gasket_land_z_mm=-d['base_plate_thickness'],
                cell_thread_tip_z_mm=-d['base_plate_thickness']-d['cell_thread_length'])


def validate(d, contact):
    for key, value in d.items():
        if isinstance(value,(int,float)) and (not math.isfinite(value) or value <= 0):
            raise ValueError(f'Invalid {key}')
    for key in ('we_xy','fixed_electrode_xy','gas_xy','mount_bolt_xy'):
        values = np.asarray(d[key],dtype=float)
        expected=(2,) if key=='we_xy' else (3,2) if key=='mount_bolt_xy' else (2,2)
        if values.shape!=expected or not np.isfinite(values).all(): raise ValueError('Invalid coordinate')
    if len(d['we_xy']) != 2 or len(d['fixed_electrode_xy']) != 2 or len(d['gas_xy']) != 2 or len(d['mount_bolt_xy']) != 3:
        raise ValueError('Expected WE, two RE/CE, two gas and three mounting positions')
    root = (d['cell_thread_nominal_diameter']-d['cell_thread_diametral_allowance'])/2-d['cell_thread_depth']
    if not 0 < d['cell_thread_diametral_allowance'] < 1:
        raise ValueError('Invalid glass thread fit allowance')
    if d['flange_diameter']/2-root < 3:
        raise ValueError('Insufficient gasket land')
    socket_r = d['we_socket_diameter']/2
    if not contact['insert_od'] < d['we_socket_diameter'] < contact['insert_flange_od'] <= d['we_pedestal_diameter']:
        raise ValueError('Insert flange does not seat on pedestal')
    if np.linalg.norm(d['we_xy'])+d['we_pedestal_diameter']/2 > d['flange_diameter']/2+1e-6:
        raise ValueError('Pedestal exceeds main flange footprint')
    if (d['we_pedestal_diameter']-d['we_socket_diameter'])/2 < 1.2:
        raise ValueError('Insufficient socket wall')
    if stack_interfaces(d,contact)['cover_to_deck_gap_mm'] < .4:
        raise ValueError('Insert wiring cover touches deck')
    cutouts = [(d['we_xy'],d['we_through_bore']/2)]
    cutouts += [(xy,(d['fixed_thread_nominal_diameter']+d['fixed_thread_diametral_allowance'])/2) for xy in d['fixed_electrode_xy']]
    cutouts += [(xy,d['gas_bore']/2) for xy in d['gas_xy']]
    for xy,r in cutouts:
        if np.linalg.norm(xy)+r+.8 > root:
            raise ValueError('Port leaves insufficient wall inside glass thread root')
    # Fixed fittings are recessed below the deck; only electrode bodies cross the
    # raised insert flange. Their head envelopes are checked separately in tests.
    for xy in d['fixed_electrode_xy']:
        separation=np.linalg.norm(np.array(xy)-d['we_xy'])
        if separation < max(socket_r+d['fixed_electrode_through_bore']/2+.3,
                            contact['insert_flange_od']/2+d['fixed_electrode_through_bore']/2+.5):
            raise ValueError('Fixed electrode interferes with WE socket or flange')
    for xy in d['gas_xy']:
        if np.linalg.norm(np.array(xy)-d['we_xy']) < contact['insert_flange_od']/2+d['gas_bore']/2+.5:
            raise ValueError('Gas tubing interferes with insert flange')
        for fixed in d['fixed_electrode_xy']:
            if np.linalg.norm(np.array(xy)-fixed) < d['fixed_fitting_head_envelope_diameter']/2+d['gas_bore']/2+.5:
                raise ValueError('Gas tubing interferes with fitting head')
    if d['fixed_fitting_head_height'] >= d['deck_thickness']:
        raise ValueError('Fitting head must remain below raised socket')
    if not d['fixed_thread_engagement'] < d['base_plate_thickness']+d['cell_thread_length']-1:
        raise ValueError('Fitting thread engagement reaches plug tip')
    if len(d['printer_bed'])!=2 or any(not math.isfinite(v) or v<=0 for v in d['printer_bed']):
        raise ValueError('Invalid printer bed')
    if not d['mount_nut_depth'] < d['mount_blind_depth'] <= d['base_plate_thickness']-1:
        raise ValueError('Mounting pockets break through gasket land')


def upper_deck(d):
    h=d['deck_thickness']; rise=d['we_socket_rise']; x,y=d['we_xy']
    pedestal=at(annulus(d['we_pedestal_diameter'],d['we_socket_diameter'],rise+.05,h-.05),[x,y,0])
    solid=union([cylinder(d['flange_diameter'],h,h/2),pedestal])
    tools=[cylinder(d['we_through_bore'],h+2,h/2,x=x,y=y)]
    for xy in d['fixed_electrode_xy']:
        tools.append(cylinder(d['fixed_fitting_access_diameter'],h+2,h/2,x=xy[0],y=xy[1]))
    for xy in d['gas_xy']:
        tools.append(cylinder(d['gas_bore'],h+2,h/2,x=xy[0],y=xy[1]))
    for xy in d['mount_bolt_xy']:
        tools.append(cylinder(d['mount_hole'],h+2,h/2,x=xy[0],y=xy[1]))
    # Open-top cable slot permits cartridge removal without threading its cable.
    tools.append(box([d['we_cable_slot_width'],8,h+rise+1-d['we_cable_slot_bottom']],
                     [x,y-d['we_pedestal_diameter']/2,(h+rise+1+d['we_cable_slot_bottom'])/2]))
    return subtract(solid,tools)


def threaded_base(d):
    t=d['base_plate_thickness']; length=d['cell_thread_length']
    major=d['cell_thread_nominal_diameter']-d['cell_thread_diametral_allowance']
    male=helical_thread(major,d['cell_thread_pitch'],d['cell_thread_depth'],length+.03,d['thread_lead_length'])
    male.apply_transform(tm.transformations.rotation_matrix(math.pi,[1,0,0]))
    male.apply_translation([0,0,-t+.03])
    solid=union([cylinder(d['flange_diameter'],t,t/-2),male])
    bottom=-t-length-1
    tools=[cylinder(d['we_through_bore'],t+length+2,bottom+(t+length+2)/2,x=d['we_xy'][0],y=d['we_xy'][1])]
    for xy in d['gas_xy']:
        tools.append(cylinder(d['gas_bore'],t+length+2,bottom+(t+length+2)/2,x=xy[0],y=xy[1]))
    for xy in d['fixed_electrode_xy']:
        tools.append(cylinder(d['fixed_electrode_through_bore'],t+length+2,bottom+(t+length+2)/2,x=xy[0],y=xy[1]))
        female=helical_thread(d['fixed_thread_nominal_diameter']+d['fixed_thread_diametral_allowance'],
                             d['fixed_thread_pitch'],d['fixed_thread_depth'],d['fixed_thread_engagement']+.1)
        female.apply_transform(tm.transformations.rotation_matrix(math.pi,[1,0,0]))
        female.apply_translation([xy[0],xy[1],.1]); tools.append(female)
    for xy in d['mount_bolt_xy']:
        angle=math.atan2(xy[1],xy[0])+math.pi/6
        nut=tm.creation.cylinder(radius=d['mount_nut_af']/math.sqrt(3),height=d['mount_nut_depth']+.1,sections=6)
        nut.apply_transform(tm.transformations.rotation_matrix(angle,[0,0,1]))
        nut.apply_translation([*xy,-d['mount_nut_depth']/2+.05]); tools.append(nut)
        tools.append(cylinder(d['mount_hole'],d['mount_blind_depth']+.1,-d['mount_blind_depth']/2+.05,x=xy[0],y=xy[1]))
    return subtract(solid,tools)


def glass_gauge(d, major):
    length=d['cell_thread_length']
    thread=helical_thread(major,d['cell_thread_pitch'],d['cell_thread_depth'],length,d['thread_lead_length'])
    solid=union([cylinder(d['flange_diameter'],2,-1),thread])
    return subtract(solid,[cylinder(36,length+4,length/2)])


def fitting_gauge(d,pitch):
    cutter=helical_thread(d['fixed_thread_nominal_diameter']+d['fixed_thread_diametral_allowance'],pitch,d['fixed_thread_depth'],10)
    return subtract(cylinder(16,8,4),[at(cutter,[0,0,-1])])


def build_parts(d,contact):
    validate(d,contact)
    old=contact_parts(contact)
    meshes={'upper_deck':upper_deck(d),'threaded_base':threaded_base(d),
            'compact_contact_insert':old['contact_insert'],'wire_cover':old['wire_cover'],
            'holder_rear':old['holder_rear'],'holder_front':old['holder_front']}
    major_default=d['cell_thread_nominal_diameter']-d['cell_thread_diametral_allowance']
    for index,major in enumerate((major_default-.4,major_default,d['cell_thread_nominal_diameter'])):
        mesh=glass_gauge(d,major);tools=[]
        for i in range(index+1):
            tool=box([4,1.5,4],[d['flange_diameter']/2-.5,0,-1])
            tool.apply_transform(tm.transformations.rotation_matrix((i-index/2)*.12,[0,0,1]));tools.append(tool)
        meshes[f'glass_thread_gauge_D{major:g}_P{d["cell_thread_pitch"]:g}']=subtract(mesh,tools)
    for index,pitch in enumerate(sorted(set((1.5,d['fixed_thread_pitch'],2.0)))):
        mesh=fitting_gauge(d,pitch);tools=[]
        for i in range(index+1):
            tool=box([3,1.2,2.5],[8,0,7])
            tool.apply_transform(tm.transformations.rotation_matrix((i-index/2)*.35,[0,0,1]));tools.append(tool)
        meshes[f'fitting_thread_gauge_P{pitch:.3f}']=subtract(mesh,tools)
    # Sub-micron boolean slivers can collapse on binary STL's float32 grid.
    # Snap only the trial gauges to 0.0001 mm and remove collapsed faces before
    # validating; this is far below FDM resolution and preserves their form.
    for name,mesh in list(meshes.items()):
        if 'gauge' not in name: continue
        clean=tm.Trimesh(vertices=np.round(mesh.vertices,4),faces=mesh.faces,process=True)
        clean.update_faces(clean.unique_faces())
        clean.update_faces(clean.nondegenerate_faces(height=1e-8))
        clean.remove_unreferenced_vertices()
        meshes[name]=clean
    return meshes


def verify_stl(path,expected_solids):
    mesh=tm.load_mesh(path)
    if not mesh.is_volume or not mesh.is_watertight or connected_solids(mesh)!=expected_solids:
        raise ValueError(f'Exported STL failed reload validation: {path.name}')


def export(d,contact,folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    meshes=build_parts(d,contact); entries=[]; positioned=[]; cursor=[5.,5.]; row=0.
    source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dependencies={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                  for name in ('fixed_contact_cad.py','electrode_holder.py')}
    geometry_id=hashlib.sha256((source+json.dumps([d,contact,dependencies],sort_keys=True)).encode()).hexdigest()[:16]
    for name,original in meshes.items():
        if not original.is_volume or not original.is_watertight or connected_solids(original)!=1:
            raise ValueError(f'{name} is not a closed connected solid')
        angle=-90 if name=='holder_rear' else 90 if name=='holder_front' else 180 if name=='threaded_base' else 0
        transform=tm.transformations.rotation_matrix(math.radians(angle),[1,0,0])
        mesh=original.copy();mesh.apply_transform(transform);transform[:3,3]=-mesh.bounds[0]
        mesh=original.copy();mesh.apply_transform(transform)
        if cursor[0]+mesh.extents[0]>d['printer_bed'][0]-5:
            cursor=[5.,cursor[1]+row+5];row=0
        if cursor[1]+mesh.extents[1]>d['printer_bed'][1]-5 or mesh.extents[2]>d['printer_height']:
            raise ValueError('Print plate exceeds printer bounds')
        mesh.export(folder/f'{name}.stl')
        verify_stl(folder/f'{name}.stl',1)
        placed=at(mesh,[*cursor,0]); positioned.append(placed)
        entries.append(dict(file=f'{name}.stl',quantity=1,size_mm=mesh.extents.tolist(),volume_mm3=float(mesh.volume),
                            connected_solids=1,watertight=True,assembly_to_print=transform.tolist(),
                            plate_translation_mm=[*cursor,0]))
        cursor[0]+=mesh.extents[0]+5;row=max(row,mesh.extents[1])
    plate=tm.util.concatenate(positioned);plate.export(folder/'complete_print_plate.stl')
    assembly_plate=tm.util.concatenate(positioned[:6]);assembly_plate.apply_translation(-assembly_plate.bounds[0])
    assembly_plate.export(folder/'cap_assembly_print_plate.stl')
    gauges=tm.util.concatenate(positioned[6:]);gauges.apply_translation(-gauges.bounds[0]);gauges.export(folder/'gauges_print_plate.stl')
    verify_stl(folder/'complete_print_plate.stl',len(meshes))
    verify_stl(folder/'cap_assembly_print_plate.stl',6)
    verify_stl(folder/'gauges_print_plate.stl',len(meshes)-6)
    manifest=dict(design=REVISION,geometry_id=geometry_id,units='mm',dimensions=d,contact_dimensions=contact,
                  source_sha256=source,dependency_sha256=dependencies,parts=entries,interfaces=stack_interfaces(d,contact),
                  plate_bounds_mm=plate.bounds.tolist(),plate_solids=connected_solids(plate),
                  assembly_frame='Z=0 upper-deck underside / threaded-base top. Glass gasket land at Z=-base_plate_thickness. +Z toward robot. XY coordinates local to cap, not robot.',
                  assembly_translations_mm={'upper_deck':[0,0,0],'threaded_base':[0,0,0],
                    'compact_contact_insert':[*d['we_xy'],stack_interfaces(d,contact)['insert_origin_z_mm']],
                    'wire_cover':[*d['we_xy'],stack_interfaces(d,contact)['cover_bottom_z_mm']],
                    'holder_rear':[*d['we_xy'],stack_interfaces(d,contact)['holder_origin_z_mm']],
                    'holder_front':[*d['we_xy'],stack_interfaces(d,contact)['holder_origin_z_mm']]},
                  warnings=['Both OEM mating thread forms are provisional. Fit gauges first; do not force printed parts into glass.',
                    'Plain annular gasket land; original gasket dimensions and compression are not verified.',
                    'RE/CE fitting heads must fit inside 13 mm access wells and stay below Z=5.5 mm.',
                    'No electrolyte/temperature compatibility, gas tightness, immersion depth or gripper clearance has been established.'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
