"""Generate provisional collar and split-clamp probe bracket; dimensions in mm.

Run: .venv/bin/python cad/gripper/generate.py
Edit dimensions.json first. No OpenSCAD installation required for STL export.
"""
import json
from pathlib import Path
import numpy as np
import trimesh as tm

HERE = Path(__file__).resolve().parent


def box(size, center):
    m = tm.creation.box(extents=size)
    m.apply_translation(center)
    return m


def cylinder(d, h, center, axis='z'):
    m = tm.creation.cylinder(radius=d / 2, height=h, sections=96)
    if axis == 'x':
        m.apply_transform(tm.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    if axis == 'y':
        m.apply_transform(tm.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    m.apply_translation(center)
    return m


def union(*parts):
    return tm.boolean.union(list(parts), engine='manifold')


def subtract(solid, *tools):
    return tm.boolean.difference([solid, *tools], engine='manifold')


def connected_solids(mesh):
    parent = list(range(len(mesh.vertices)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in mesh.faces:
        parent[root(int(b))] = root(int(a))
        parent[root(int(c))] = root(int(a))
    return len({root(int(i)) for i in np.unique(mesh.faces)})


def validate(p):
    if any(not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0 for v in p.values()):
        raise ValueError('All dimensions must be finite and positive')
    bore = p['rod_diameter'] + p['rod_diametral_clearance']
    if p['collar_diameter'] < bore + 4:
        raise ValueError('Collar requires at least 2 mm radial wall')
    if p['flange_diameter'] < p['collar_diameter'] + 2:
        raise ValueError('Flange must overhang the collar')
    if p['pad_diameter'] + p['pad_clearance'] > p['flange_diameter'] - 4:
        raise ValueError('Pad recess leaves insufficient flange wall')
    if p['pad_recess_depth'] >= p['flange_thickness'] - 1:
        raise ValueError('Pad recess must leave at least 1 mm floor')
    if p['probe_hole_diameter'] > p['probe_plate_width'] - 4:
        raise ValueError('Probe plate needs at least 2 mm around hole')
    if p['bracket_drop'] <= p['clamp_height'] / 2 + p['arm_thickness']:
        raise ValueError('Probe plate must sit below clamp')
    if p['route_offset'] <= (p['mount_neck_diameter'] + p['mount_clearance']) / 2 + p['clamp_wall']:
        raise ValueError('Bracket route must lie outside clamp')
    if p['flange_thickness'] + p['collar_height'] <= p['rod_socket_depth']:
        raise ValueError('Rod socket must stop below contact pad floor')
    if p['rod_socket_depth'] >= p['collar_height'] + p['flange_thickness'] - p['pad_recess_depth'] - 1:
        raise ValueError('Leave at least 1 mm between rod socket and pad recess')


def build(p):
    validate(p)
    h, ft = p['collar_height'], p['flange_thickness']
    total = h + ft
    collar = union(cylinder(p['collar_diameter'], h, [0, 0, h / 2]),
                   cylinder(p['flange_diameter'], ft, [0, 0, h + ft / 2]))
    # Blind socket retains a contact-pad floor. Small axial wire hole joins them.
    collar = subtract(collar,
        cylinder(p['rod_diameter'] + p['rod_diametral_clearance'], p['rod_socket_depth'] + .2,
                 [0, 0, p['rod_socket_depth'] / 2 - .1]),
        cylinder(p['wire_hole_diameter'], total + 2, [0, 0, total / 2]),
        cylinder(p['pad_diameter'] + p['pad_clearance'], p['pad_recess_depth'] + .2,
                 [0, 0, total - p['pad_recess_depth'] / 2 + .1]),
        cylinder(p['rod_set_screw_hole'], p['collar_diameter'],
                 [p['collar_diameter'] / 2, 0, p['rod_socket_depth'] / 2], 'x'))

    ri = (p['mount_neck_diameter'] + p['mount_clearance']) / 2
    ro, ch = ri + p['clamp_wall'], p['clamp_height']
    ring = subtract(cylinder(ro * 2, ch, [0, 0, 0]),
                    cylinder(ri * 2, ch + 2, [0, 0, 0]))
    gap, tab = p['clamp_split_gap'], p['clamp_tab_width']
    halves = []
    for sign in (1, -1):
        halfspace = box([4 * ro, 2 * ro, ch + 2], [0, sign * (ro + gap / 2), 0])
        half = tm.boolean.intersection([ring, halfspace], engine='manifold')
        # Tabs overlap the annulus at x=ro; clamp bolts run along Y.
        for x in (-ro, ro):
            half = union(half, box([tab, p['clamp_tab_depth'], ch],
                         [x, sign * (gap / 2 + p['clamp_tab_depth'] / 2), 0]))
            half = subtract(half, cylinder(p['clamp_bolt_hole'], 2 * p['clamp_tab_depth'] + 4,
                            [x, 0, 0], 'y'))
        halves.append(half)

    # C-shaped route: outward from front clamp, down outside the finger sweep,
    # then inward to the probe axis. Actual finger envelope must be measured.
    w, t, drop = p['arm_width'], p['arm_thickness'], p['bracket_drop']
    offset = p['route_offset']
    top = box([w, offset - ri + t, t], [0, (ri + offset) / 2, 0])
    upright = box([w, t, drop + t], [0, offset, -drop / 2])
    lower = box([w, offset + t, t], [0, offset / 2, -drop])
    plate = cylinder(p['probe_plate_width'], t, [0, 0, -drop])
    front = union(halves[0], top, upright, lower, plate)
    front = subtract(front, cylinder(p['probe_hole_diameter'], t + 2, [0, 0, -drop]))
    # Cable-tie holes near the external upright; keep lead clear of soft fingers.
    for z in (-drop / 3, -2 * drop / 3):
        front = subtract(front, cylinder(p['cable_tie_hole'], t + 2, [0, offset, z], 'y'))
    return {'pickup_collar': collar, 'probe_bracket_front': front, 'probe_bracket_rear': halves[1]}


def preview(meshes):
    """Standalone orthographic SVG, rendered to PNG with the installed Qt runtime."""
    colors = ['#15a798', '#d3dee5', '#9daeb9']
    panels = []
    # Separate views keep the mating clamp faces visible; no implied assembly fit.
    for i, (name, mesh) in enumerate(meshes.items()):
        rx = tm.transformations.rotation_matrix(np.deg2rad(-65), [1, 0, 0])
        rz = tm.transformations.rotation_matrix(np.deg2rad(-30), [0, 0, 1])
        v = tm.transformations.transform_points(mesh.vertices, rx @ rz)
        lo, hi = v[:, :2].min(axis=0), v[:, :2].max(axis=0)
        scale = min(310 / (hi[0] - lo[0]), 330 / (hi[1] - lo[1]))
        xy = (v[:, :2] - (lo + hi) / 2) * scale
        xy[:, 1] *= -1
        xy += [200 + i * 400, 285]
        polys = []
        for face in sorted(mesh.faces, key=lambda f: v[f, 2].mean()):
            pts = ' '.join(f'{x:.2f},{y:.2f}' for x, y in xy[face])
            polys.append(f'<polygon points="{pts}" fill="{colors[i]}" stroke="#35515e" stroke-width="0.3"/>')
        panels.append(''.join(polys) + f'<text x="{200 + i * 400}" y="500" text-anchor="middle" font-size="20">{name.replace("_", " ")}</text>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="570" viewBox="0 0 1200 570"><rect width="1200" height="570" fill="#f7fafb"/><g font-family="sans-serif" fill="#163847"><text x="30" y="40" font-size="28">Printable gripper parts — provisional dimensions</text>' + ''.join(panels) + '<text x="30" y="550" font-size="16">Separate parts shown. Verify mounting neck, finger clearance and probe dimensions before use.</text></g></svg>'
    (HERE / 'parts-preview.svg').write_text(svg)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    app = QApplication.instance() or QApplication([])
    img = QImage(1200, 570, QImage.Format.Format_ARGB32)
    img.fill(0xffffffff)
    painter = QPainter(img)
    QSvgRenderer(str(HERE / 'parts-preview.svg')).render(painter)
    painter.end()
    img.save(str(HERE / 'parts-preview.png'))


if __name__ == '__main__':
    params = json.loads((HERE / 'dimensions.json').read_text())
    parts = build(params)
    report = {}
    for name, mesh in parts.items():
        count = connected_solids(mesh)
        if not mesh.is_watertight or not mesh.is_volume or count != 1:
            raise ValueError(f'{name}: expected one closed connected solid')
        mesh.export(HERE / f'{name}.stl')
        report[name] = {'watertight': bool(mesh.is_watertight), 'connected_solids': count,
                        'volume_mm3': round(float(mesh.volume), 2), 'bounds_mm': mesh.bounds.tolist()}
    (HERE / 'mesh-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    preview(parts)
    print(json.dumps(report, indent=2))
