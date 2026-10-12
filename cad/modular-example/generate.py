"""Regenerate the example and a mesh-based assembly preview; run from repo root."""
import json
import sys
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from electrobot.config import Settings
from electrobot.rack_cad import export_rack

folder=Path(__file__).resolve().parent
config=folder/'example-config.json'
if config.exists(): s=Settings(**json.loads(config.read_text()))
else:
    s=Settings(rack_design='lattice',rack_layout='radial',rack_columns=8,electrodes=24,
               rack_pitch=36,rack_angle_step=11,rack_start_angle=-30,rack_module_slots=4,
               cell_x=150,cell_y=140,rinse_x=150,rinse_y=-150)
config.write_text(json.dumps(asdict(s),indent=2)+'\n')
export_rack(s,folder)
meta=json.loads((folder/'rack_manifest.json').read_text())

import numpy as np
import trimesh as tm
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter,QImage,QColor,QPolygonF,QFont
app=QApplication.instance() or QApplication([])
objects=[]
for m in meta['modules']:
    rotation=tm.transformations.rotation_matrix(np.radians(m['rotation_deg']),[0,0,1])
    top=tm.load_mesh(folder/m['file']); top.apply_transform(rotation); top.apply_translation([*m['robot_xy_at_stl_origin'],meta['foot_height_mm']]); objects.append((top,'#3285a8'))
    for x,y in m['foot_centers_robot_xy']:
        foot=tm.load_mesh(folder/'rack_foot.stl'); foot.apply_translation([-meta['foot_center_local_xy'][0],-meta['foot_center_local_xy'][1],0]); foot.apply_transform(rotation); foot.apply_translation([x,y,0]); objects.append((foot,'#0e9f92'))
# Show only three holders so the top and feet remain visible.
for x,y,z in meta['slot_robot_xyz'][:3]:
    holder=tm.load_mesh(folder/'pickup_holder.stl')
    transform=np.diag([1,-1,-1,1]); holder.apply_transform(transform)
    holder.apply_translation([x-s.holder_flange_diameter/2,y+s.holder_flange_diameter/2,meta['seat_height_mm']+s.holder_height+s.holder_flange_thickness])
    objects.append((holder,'#8879ba'))
    rod=tm.creation.cylinder(radius=s.rod_diameter/2,height=s.rack_hanging_length,sections=24)
    rod.apply_translation([x,y,s.rack_tip_clearance+s.rack_hanging_length/2]); objects.append((rod,'#50616c'))
direction=np.array([.48,-.66,.57]); direction/=np.linalg.norm(direction)
horizontal=np.cross([0,0,1],direction); horizontal/=np.linalg.norm(horizontal)
up=np.cross(direction,horizontal)
triangles=[]; all_xy=[]
for mesh,color in objects:
    vertices=mesh.vertices; xy=np.column_stack((vertices@horizontal,-vertices@up)); depth=vertices@direction
    all_xy.append(xy)
    for face,normal in zip(mesh.faces,mesh.face_normals):
        if normal@direction<=0: continue
        shade=.65+.35*max(0,normal@np.array([.25,-.4,.88]))
        base=QColor(color); c=QColor.fromRgbF(min(1,base.redF()*shade),min(1,base.greenF()*shade),min(1,base.blueF()*shade))
        triangles.append((float(depth[face].mean()),xy[face],c))
coords=np.vstack(all_xy); lo=coords.min(axis=0); hi=coords.max(axis=0)
factor=min(1080/(hi[0]-lo[0]),590/(hi[1]-lo[1])); offset=np.array([(1200-(hi[0]-lo[0])*factor)/2,115])
image=QImage(1200,800,QImage.Format.Format_RGB32); image.fill(QColor('#f4f8fa')); painter=QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.setPen(QColor('#234452')); font=QFont(); font.setPixelSize(27); painter.setFont(font)
painter.drawText(35,42,'Modular rack · 24 radial seats · provisional dimensions')
font.setPixelSize(18); painter.setFont(font); painter.drawText(35,74,'Blue: six top modules   Green: 18 reusable fork feet   Purple: example pickup holders')
for depth,xy,color in sorted(triangles,key=lambda item:item[0]):
    points=(xy-lo)*factor+offset; painter.setPen(color); painter.setBrush(color); painter.drawPolygon(QPolygonF([QPointF(*point) for point in points]))
painter.setPen(QColor('#234452')); painter.drawText(35,752,'Mesh-based assembly preview. Three holders shown; rods hang clear of the bench.')
painter.drawText(35,781,'Each module must be secured to the bench. Trial-print the fit coupon, one foot and one holder first.')
painter.end(); image.save(str(folder/'assembly-preview.png'))
print(json.dumps({'modules':len(meta['modules']),'feet':meta['foot_quantity'],'parts':[(p['file'],p['quantity'],p['size_mm']) for p in meta['parts']],'rack_volume_mm3':meta['rack_solid_volume_mm3']},indent=2))
