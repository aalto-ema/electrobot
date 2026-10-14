"""Standalone dry-bench fixed-contact prototype, independent of lab Settings."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import trimesh as tm
from shapely.geometry import LineString

from .electrode_holder import box, cylinder
from .mesh_utils import connected_solids

REVISION = 'fixed-contact-v1'


def union(parts):
    return tm.boolean.union(parts, engine='manifold')


def subtract(solid, tools):
    return tm.boolean.difference([solid, *tools], engine='manifold')


def annulus(od, inner, height, bottom=0):
    return subtract(cylinder(od, height, bottom + height / 2),
                    [cylinder(inner, height + 2, bottom + height / 2)])


def validate(d):
    for key, value in d.items():
        if isinstance(value, (int, float)) and (not math.isfinite(value) or (value <= 0 and key != 'holder_wire_y')):
            raise ValueError(f'Invalid {key}')
    if not d['electrode_diameter'] < d['holder_bore'] < d['washer_id'] < d['washer_od'] < d['holder_lower_diameter'] < d['insert_id'] < d['holder_grip_diameter'] < d['holder_flange_diameter']:
        raise ValueError('Bore, washer and holder interfaces are incompatible')
    if not d['wire_max_od'] < d['wire_hole'] <= d['wire_groove_width']:
        raise ValueError('Wire clearance is invalid')
    if abs(d['holder_wire_y']) - d['wire_hole'] / 2 <= d['holder_bore'] / 2 + .5:
        raise ValueError('Wire passage is too close to electrode bore')
    if abs(d['holder_wire_y']) + 1.5 >= d['holder_lower_diameter'] / 2:
        raise ValueError('Wire joint pocket leaves insufficient outer wall')
    if not 0 < d['split_gap'] < d['holder_bore'] / 4:
        raise ValueError('Invalid split gap')
    if not d['holder_bore']/2 + d['bolt_hole']/2 + .5 < d['bolt_x'] < d['holder_grip_diameter']/2 - d['bolt_hole']/2 - .5:
        raise ValueError('Bolt holes intersect bore or outer wall')
    if not d['holder_lower_height'] + d['holder_flange_height'] + 3 < d['bolt_z'] < d['holder_height'] - 3:
        raise ValueError('Bolt pockets leave insufficient holder wall')
    if not d['wire_groove_depth'] + 1 < d['insert_floor'] - d['bar_seat_depth']:
        raise ValueError('Wire groove and bar seat leave insufficient floor')
    if not 0 < d['bar_seat_depth'] < d['bar_thickness']:
        raise ValueError('Bars must stand proud of the insert floor')
    if not d['insert_through_hole']/2 < d['bar_inner_x'] < d['washer_od']/2:
        raise ValueError('Bars must clear the electrode hole and reach the washer')
    if d['bar_inner_x'] + d['bar_length'] + d['bar_slot_clearance']/2 >= d['insert_od']/2:
        raise ValueError('Bar slots break through insert exterior')
    if not d['insert_od'] < d['stand_socket_diameter'] < d['insert_flange_od'] < d['stand_od']:
        raise ValueError('Invalid stand docking interface')
    if interface(d)['flange_to_insert_rim_gap_mm'] <= .5:
        raise ValueError('Holder flange would stop seating before metal contact')
    if interface(d)['estimated_tip_clearance_above_bench_mm'] <= 10:
        raise ValueError('Insufficient estimated bench tip clearance')
    if len(d['printer_bed']) != 2 or any(not math.isfinite(v) or v <= 0 for v in d['printer_bed']):
        raise ValueError('Invalid printer bed')


def interface(d):
    bar_top = d['insert_floor'] - d['bar_seat_depth'] + d['bar_thickness']
    holder_bottom = bar_top + d['washer_thickness']
    insert_on_stand = d['stand_height'] - (d['insert_height'] - d['insert_flange_height'])
    return dict(bar_contact_z_mm=bar_top, holder_bottom_z_mm=holder_bottom,
                holder_diametral_clearance_mm=d['insert_id']-d['holder_lower_diameter'],
                flange_to_insert_rim_gap_mm=holder_bottom+d['holder_lower_height']-d['insert_height'],
                insert_on_stand_z_mm=insert_on_stand,
                estimated_tip_clearance_above_bench_mm=insert_on_stand+holder_bottom+d['holder_height']-d['electrode_length_estimate'],
                contact_note='Nominal metal-to-metal plane; glue thickness and actual tolerances are not included.')


def holder_halves(d):
    h = d['holder_height']; low = d['holder_lower_height']; diameter = d['holder_grip_diameter']
    solid = union([cylinder(d['holder_lower_diameter'], low+.1, (low+.1)/2),
                   cylinder(diameter, h-low, (h+low)/2),
                   cylinder(d['holder_flange_diameter'], d['holder_flange_height'], low+d['holder_flange_height']/2)])
    tools = [cylinder(d['holder_bore'], h+2, h/2),
             box([60, d['split_gap'], h+2], [0, 0, h/2]),
             cylinder(d['wire_hole'], h+2, h/2, y=d['holder_wire_y']),
             cylinder(3.0, 1.7, .65, y=d['holder_wire_y'])]
    for sign in (-1, 1):
        tools.append(cylinder(d['bolt_hole'], diameter+4, d['bolt_z'], axis='y', x=sign*d['bolt_x']))
        for side in (-1, 1):
            tools.append(box([8, diameter, 6], [sign*d['bolt_x'], side*(d['bolt_flat_y']+diameter/2), d['bolt_z']]))
        nut = tm.creation.cylinder(radius=d['nut_af']/math.sqrt(3), height=d['nut_depth']+.2, sections=6)
        nut.apply_transform(tm.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
        nut.apply_translation([sign*d['bolt_x'], d['bolt_flat_y']-d['nut_depth']/2+.05, d['bolt_z']])
        tools.append(nut)
    cut = subtract(solid, tools)
    return [tm.boolean.intersection([cut, box([60, 40, h+4], [0, side*20, h/2])], engine='manifold')
            for side in (-1, 1)]


def wire_routes(d):
    # Symmetric underside channels, each from a bar tail to the rear junction.
    r = d['wire_route_radius']
    routes = []
    for angles in (np.linspace(0, -math.pi/2, 40), np.linspace(-math.pi, -math.pi/2, 40)):
        line = LineString([(r*math.cos(a), r*math.sin(a)) for a in angles])
        mesh = tm.creation.extrude_polygon(line.buffer(d['wire_groove_width']/2), d['wire_groove_depth']+.1)
        mesh.apply_translation([0, 0, -.1]); routes.append(mesh)
    return routes


def insert(d):
    h = d['insert_height']; floor = d['insert_floor']; seat = floor-d['bar_seat_depth']
    solid = union([cylinder(d['insert_od'], h, h/2),
                   cylinder(d['insert_flange_od'], d['insert_flange_height'], h-d['insert_flange_height']/2)])
    # Chamfered guide entrance, with the same minimum bore below the chamfer.
    mouth = tm.creation.revolve(np.array([[0, h-1], [d['insert_id']/2, h-1],
                [d['insert_id']/2+1, h], [d['insert_id']/2+1, h+1], [0, h+1]]), sections=96)
    tools = [cylinder(d['insert_id'], h-floor+2, (h+floor)/2+1), mouth,
             cylinder(d['insert_through_hole'], h+2, h/2), *wire_routes(d),
             box([5, 4, 2.2], [0, -d['wire_route_radius'], 1]),
             box([3, 8, 2.2], [0, -d['insert_od']/2, 1])]
    for side in (-1, 1):
        # Slots open upward through the rim for installing flat stock without bending it.
        tools.append(box([d['bar_length']+d['bar_slot_clearance'], d['bar_width']+d['bar_slot_clearance'], h+2-seat],
                         [side*(d['bar_inner_x']+d['bar_length']/2), 0, (h+2+seat)/2]))
        tools.append(cylinder(d['wire_groove_width'], floor+1, floor/2, x=side*d['wire_route_radius']))
        # Solder relief below the bar tail, away from the contact area.
        tools.append(box([3, 3, 1.1], [side*d['wire_route_radius'], 0, seat-.45]))
    return subtract(solid, tools)


def metal_parts(d):
    z = interface(d)['bar_contact_z_mm']
    ring = annulus(d['washer_od'], d['washer_id'], d['washer_thickness'], z)
    bars = [box([d['bar_length'], d['bar_width'], d['bar_thickness']],
                [side*(d['bar_inner_x']+d['bar_length']/2), 0, z-d['bar_thickness']/2]) for side in (-1, 1)]
    return ring, bars


def stand(d):
    top = annulus(d['stand_od'], d['stand_socket_diameter'], d['stand_top_thickness'], d['stand_height']-d['stand_top_thickness'])
    legs = [cylinder(d['stand_leg_diameter'], d['stand_height']-d['stand_top_thickness']+1,
                     (d['stand_height']-d['stand_top_thickness']+1)/2,
                     x=d['stand_leg_radius']*math.cos(a), y=d['stand_leg_radius']*math.sin(a))
            for a in (math.pi/2, 7*math.pi/6, 11*math.pi/6)]
    return union([top, *legs])


def parts(d):
    validate(d)
    rear, front = holder_halves(d)
    cover = subtract(annulus(d['insert_od'], d['insert_through_hole'], d['cover_thickness']),
                     [box([3, 10, 4], [0, -d['insert_od']/2, 0])])
    coupon = subtract(box([24, 18, 4], [0, 0, 2]), [box([3, 3, 6], [-12, -9, 2])])
    for x, clearance, hole in ((-7, 0, 1.6), (0, .3, 1.8), (7, .6, 2.0)):
        coupon = subtract(coupon, [box([d['bar_width']+clearance, d['bar_length']+.3, 2], [x, -1, 4.4]),
                                   cylinder(hole, 6, 2, x=x, y=6.5)])
    bore = subtract(cylinder(d['holder_grip_diameter'], 4, 2),
                    [cylinder(d['holder_bore'], 6, 2), box([30, d['split_gap'], 6], [0, 0, 2])])
    bore_halves = [tm.boolean.intersection([bore, box([30, 30, 8], [0, side*15, 2])], engine='manifold') for side in (-1, 1)]
    socket_coupon = annulus(26, d['insert_id'], 4)
    return {'holder_rear': rear, 'holder_front': front, 'contact_insert': insert(d),
            'wire_cover': cover, 'bench_stand': stand(d), 'bar_wire_coupon': coupon,
            'bore_coupon_rear': bore_halves[0], 'bore_coupon_front': bore_halves[1],
            'socket_fit_coupon': socket_coupon}


def export(d, folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    meshes = parts(d); entries = []; plate = []; cursor = np.array([5., 5.]); row_height = 0
    for name, original in meshes.items():
        if not original.is_watertight or not original.is_volume or connected_solids(original) != 1:
            raise ValueError(f'{name} is not a closed connected solid')
        rotation = -90 if name.endswith('_rear') else 90 if name.endswith('_front') else 180 if name == 'bench_stand' else 0
        transform = tm.transformations.rotation_matrix(math.radians(rotation), [1, 0, 0])
        mesh = original.copy(); mesh.apply_transform(transform)
        transform[:3, 3] = -mesh.bounds[0]
        mesh = original.copy(); mesh.apply_transform(transform)
        if mesh.extents[2] > d['printer_height']:
            raise ValueError(f'{name} exceeds printer height')
        if cursor[0]+mesh.extents[0] > d['printer_bed'][0]-5:
            cursor = np.array([5., cursor[1]+row_height+5]); row_height = 0
        if cursor[1]+mesh.extents[1] > d['printer_bed'][1]-5:
            raise ValueError('Kit exceeds print bed')
        mesh.export(folder/f'{name}.stl')
        positioned = mesh.copy(); positioned.apply_translation([*cursor, 0]); plate.append(positioned)
        entries.append(dict(file=f'{name}.stl', quantity=1, size_mm=mesh.extents.tolist(),
                            volume_mm3=float(mesh.volume), connected_solids=1, watertight=True,
                            assembly_to_print=transform.tolist(), plate_translation_mm=[*cursor.tolist(), 0]))
        cursor[0] += mesh.extents[0]+5; row_height = max(row_height, mesh.extents[1])
    kit = tm.util.concatenate(plate); kit.export(folder/'complete_print_plate.stl')
    fit_plate = tm.util.concatenate([plate[i] for i, name in enumerate(meshes) if 'coupon' in name])
    fit_plate.apply_translation(-fit_plate.bounds[0]); fit_plate.export(folder/'coupons_print_plate.stl')
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cfg_hash = hashlib.sha256((REVISION+source_hash+json.dumps(d, sort_keys=True)).encode()).hexdigest()[:16]
    manifest = dict(design=REVISION, units='mm', geometry_id=cfg_hash, dimensions=d, parts=entries,
                    interfaces=interface(d),
                    coordinate_frames='Holder: Z=0 plastic bottom, +Z toward terminal. Insert: Z=0 underside. Stand: Z=0 feet. Cover: Z=0 lower face; installed at Z=-cover_thickness below insert.',
                    plate_bounds_mm=kit.bounds.tolist(), plate_solids=connected_solids(kit),
                    source_sha256=source_hash,
                    purchased_parts=['1 copper washer 8 mm ID x 14 mm OD x 1 mm',
                                     '2 copper tabs 5 x 10 x 1 mm, cut and deburred from flat sheet',
                                     'insulated flexible wire with OD <=1.4 mm (e.g. suitable 26 AWG hook-up wire; verify insulation OD)',
                                     '2 M3 x 12 bolts, 2 M3 hex nuts, 2 compact M3 washers OD <=6 mm',
                                     'terminal socket matched to actual electrode pin; size still unmeasured',
                                     'small amount of adhesive for washer and bars; insulating tape for removable cover'],
                    warning='Dry bench prototype. No validated cell-cap fit, liquid seal, gripper retention or electrical contact. Estimated tip clearance depends on actual electrode length.')
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest
