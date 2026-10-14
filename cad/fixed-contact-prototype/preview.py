"""Orthographic previews of actual generated meshes; optional metal/rod overlays."""
import numpy as np
import trimesh as tm
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QImage, QColor, QFont
from electrobot.fixed_contact_cad import parts, metal_parts, interface, cylinder


def render_panels(panels, target, title, subtitle):
    app = QApplication.instance() or QApplication([])
    image = QImage(1500, 1160, QImage.Format_RGB32); image.fill(QColor('#f4f7fa'))
    p = QPainter(image); p.setRenderHint(QPainter.Antialiasing)
    font = QFont('Arial'); font.setPixelSize(30); p.setFont(font); p.setPen(QColor('#253d50'))
    p.drawText(30, 43, title)
    font.setPixelSize(18); p.setFont(font); p.drawText(30, 76, subtitle)
    for index, (heading, objects, direction, note) in enumerate(panels):
        col = index % 2; row = index // 2
        origin = np.array([col*750+35, row*510+145])
        p.setPen(QColor('#253d50')); font.setPixelSize(23); p.setFont(font)
        p.drawText(int(origin[0]), int(origin[1]-25), heading)
        direction = np.array(direction, dtype=float); direction /= np.linalg.norm(direction)
        horizontal = np.cross([0, 0, 1], direction); horizontal /= np.linalg.norm(horizontal)
        up = np.cross(direction, horizontal)
        all_coords = []; triangles = []
        for mesh, color in objects:
            coords = np.column_stack((mesh.vertices@horizontal, -mesh.vertices@up))
            all_coords.append(coords); depth = mesh.vertices@direction
            for face, normal in zip(mesh.faces, mesh.face_normals):
                if normal@direction <= 0: continue
                shade = .55+.45*max(0, normal@direction)
                base = QColor(color); tint = QColor.fromRgbF(base.redF()*shade, base.greenF()*shade, base.blueF()*shade)
                triangles.append((depth[face], coords[face], tint))
        coords = np.vstack(all_coords); lo = coords.min(axis=0); size = coords.max(axis=0)-lo
        scale = min(665/size[0], 385/size[1]); offset = np.array([(670-size[0]*scale)/2, 2.])
        pixels = np.full((395, 670, 3), [244, 247, 250], dtype=np.uint8)
        zbuffer = np.full((395, 670), -np.inf)
        for depths, coords, color in triangles:
            xy = (coords-lo)*scale+offset
            xmin, ymin = np.maximum(np.floor(xy.min(axis=0)).astype(int), [0, 0])
            xmax, ymax = np.minimum(np.ceil(xy.max(axis=0)).astype(int), [669, 394])
            if xmax < xmin or ymax < ymin: continue
            a, b, c = xy
            denom = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denom) < 1e-9: continue
            yy, xx = np.mgrid[ymin:ymax+1, xmin:xmax+1]
            xx = xx+.5; yy = yy+.5
            wa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/denom
            wb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/denom
            wc = 1-wa-wb
            depth = wa*depths[0]+wb*depths[1]+wc*depths[2]
            region = zbuffer[ymin:ymax+1, xmin:xmax+1]
            mask = (wa >= -1e-7) & (wb >= -1e-7) & (wc >= -1e-7) & (depth > region)
            region[mask] = depth[mask]
            pixels[ymin:ymax+1, xmin:xmax+1][mask] = [color.red(), color.green(), color.blue()]
        panel_image = QImage(pixels.data, 670, 395, pixels.strides[0], QImage.Format_RGB888).copy()
        p.drawImage(int(origin[0]), int(origin[1]), panel_image)
        p.setPen(QColor('#253d50')); font.setPixelSize(17); p.setFont(font)
        p.drawText(int(origin[0]), int(origin[1]+427), note)
    p.setPen(QColor('#253d50')); font.setPixelSize(18); p.setFont(font)
    p.drawText(30, 1132, 'Prototype in mm. Metal parts are purchased. No demonstrated physical fit, contact resistance or liquid sealing.')
    p.end(); image.save(str(target))


def preview(d, folder):
    meshes = parts(d); fit = interface(d); ring, bars = metal_parts(d)
    def moved(mesh, xyz):
        mesh = mesh.copy(); mesh.apply_translation(xyz); return mesh
    assembled = [(meshes['bench_stand'], '#a6b7c6')]
    assembled += [(moved(meshes['contact_insert'], [0, 0, fit['insert_on_stand_z_mm']]), '#6cae99')]
    for name in ('holder_rear', 'holder_front'):
        assembled.append((moved(meshes[name], [0, 0, fit['insert_on_stand_z_mm']+fit['holder_bottom_z_mm']]), '#a38bc8'))
    assembled += [(moved(m, [0, 0, fit['insert_on_stand_z_mm']]), '#c68d43') for m in (ring, *bars)]
    top = fit['insert_on_stand_z_mm']+fit['holder_bottom_z_mm']+d['holder_height']
    assembled.append((cylinder(d['electrode_diameter'], d['electrode_length_estimate'], top-d['electrode_length_estimate']/2), '#425668'))
    # Expose the actual wire passage and terminal bore in the rear half.
    exploded = [(moved(meshes['holder_rear'], [0, -7, 0]), '#a38bc8'),
                (moved(meshes['holder_front'], [0, 7, 0]), '#b5a3d4'),
                (moved(ring, [0, 0, -fit['holder_bottom_z_mm']-4]), '#c68d43')]
    top_insert = [(meshes['contact_insert'], '#80bca6'), *[(bar, '#c68d43') for bar in bars]]
    underside = [(meshes['contact_insert'], '#80bca6'),
                 (moved(meshes['wire_cover'], [43, 0, -3]), '#a8cfc0')]
    render_panels([
        ('A. Assembled on the dry-test stand', assembled, [.6, -.9, .65], 'Estimated tip clearance: 17.8 mm for a 60 mm electrode body.'),
        ('B. Split holder + bottom copper washer', exploded, [.65, .8, -.55], 'Rear half includes the 1.8 mm wire passage and joint recess.'),
        ('C. Insert top + two fixed copper tabs', top_insert, [.2, -.3, 2.0], 'Tabs are 5 x 10 x 1 mm; open slots allow top installation.'),
        ('D. Underside wire routes + separate cover', underside, [.55, .75, -1.1], 'Two channels meet at the rear junction; cover is taped in place.')
    ], folder/'assembly-preview.png', 'Fixed-contact prototype — exact CAD mesh views',
       'Purple: split holder  |  Green: insert / cover  |  Orange: copper parts  |  Grey: stand and illustrative electrode')
    # Render the actual plate with every printed part, in their export coordinates.
    import json
    manifest = json.loads((folder/'manifest.json').read_text())
    all_parts = []
    for entry in manifest['parts']:
        mesh = tm.load_mesh(folder/entry['file']); mesh.apply_translation(entry['plate_translation_mm'])
        color = '#a38bc8' if 'holder' in entry['file'] else '#80bca6' if 'insert' in entry['file'] or 'cover' in entry['file'] else '#a6b7c6'
        all_parts.append((mesh, color))
    render_panels([
        ('Complete plate — 9 printed solids', all_parts, [.15, -.3, 1.6], 'Print All at Once. Stand is intentionally upside down.'),
        ('Holder halves — split faces on the bed', [(tm.load_mesh(folder/'holder_rear.stl'), '#a38bc8'),
            (moved(tm.load_mesh(folder/'holder_front.stl'), [31, 0, 0]), '#b5a3d4')], [.5, -.8, .9], 'Short bridges: bore and small wire passage; inspect in Cura.'),
        ('Fast fit coupons', [(tm.load_mesh(folder/'coupons_print_plate.stl'), '#a6b7c6')], [.2, -.5, 1.2], 'Bore pair + 18.6 mm socket ring + bar/wire coupon.'),
        ('Insert and cover — underside details', underside, [.3, .8, -1.3], 'Insert prints open cup upward; 2 mm underside grooves bridge.')
    ], folder/'print-preview.png', 'Print orientations and fit checks',
       'STL units: mm  |  Nominal 220 x 220 x 250 mm printer  |  0.2 mm layers suggested for the first fit trial')
