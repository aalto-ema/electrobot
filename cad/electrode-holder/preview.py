"""Orthographic mesh preview: exact exported carrier geometry, illustrative electrode."""
import numpy as np
import trimesh as tm
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter,QImage,QColor,QPolygonF,QFont
from electrobot.electrode_holder import holder_halves,cylinder


def preview(d,folder):
    app=QApplication.instance() or QApplication([])
    image=QImage(1400,850,QImage.Format.Format_RGB32); image.fill(QColor('#f4f8fa'))
    p=QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font=QFont(); font.setPixelSize(28); p.setFont(font); p.setPen(QColor('#234452'))
    p.drawText(35,43,'Split electrode carrier · exact mesh preview · prototype dimensions')
    font.setPixelSize(18); p.setFont(font)
    p.drawText(35,75,'Purple: printed halves   Grey: 6 mm body   Gold: estimated terminal (width illustrative)   Orange: foil band')
    direction=np.array([.5,-.75,.55]); direction/=np.linalg.norm(direction)
    horizontal=np.cross([0,0,1],direction); horizontal/=np.linalg.norm(horizontal); up=np.cross(direction,horizontal)
    halves=holder_halves(d)
    for panel,title in enumerate(('Assembled carrier','Exploded halves + electrode','Print orientation · split faces down')):
        objects=[]; h=d['total_height']
        if panel<2:
            for sign,half in zip((-1,1),halves):
                half=half.copy()
                if panel==1: half.apply_translation([0,sign*11,0])
                objects.append((half,'#9480ba'))
            rod=cylinder(d['electrode_body_diameter'],d['electrode_body_length_estimate'],
                         h-d['electrode_body_length_estimate']/2)
            pin=cylinder(1.2,d['terminal_length_estimate'],h+d['terminal_length_estimate']/2)
            objects.extend(((rod,'#435665'),(pin,'#d4aa43')))
            if panel==0:
                outer=cylinder(d['body_diameter']-2*d['contact_recess']+.2,d['contact_width'],d['contact_z']+d['contact_width']/2)
                inner=cylinder(d['body_diameter']-2*d['contact_recess'],d['contact_width']+1,d['contact_z']+d['contact_width']/2)
                objects.append((tm.boolean.difference([outer,inner],engine='manifold'),'#cb883d'))
        else:
            for i,label in enumerate(('rear','front')):
                mesh=tm.load_mesh(folder/f'holder_{label}.stl'); mesh.apply_translation([i*32,0,0]); objects.append((mesh,'#9480ba'))
        triangles=[]; coords=[]
        for mesh,color in objects:
            xy=np.column_stack((mesh.vertices@horizontal,-mesh.vertices@up)); depth=mesh.vertices@direction; coords.append(xy)
            for face,normal in zip(mesh.faces,mesh.face_normals):
                if normal@direction<=0: continue
                shade=.55+.45*max(0,normal@np.array([.25,-.4,.88]))
                base=QColor(color); tint=QColor.fromRgbF(base.redF()*shade,base.greenF()*shade,base.blueF()*shade)
                triangles.append((depth[face].mean(),xy[face],tint))
        coords=np.vstack(coords); lo=coords.min(axis=0); hi=coords.max(axis=0)
        scale=min(390/(hi[0]-lo[0]),570/(hi[1]-lo[1]))
        offset=np.array([panel*460+40+(390-(hi[0]-lo[0])*scale)/2,155+(570-(hi[1]-lo[1])*scale)/2])
        p.setPen(QColor('#234452')); p.drawText(panel*460+35,120,title)
        for depth,xy,color in sorted(triangles,key=lambda item:item[0]):
            p.setPen(color); p.setBrush(color)
            p.drawPolygon(QPolygonF([QPointF(*point) for point in (xy-lo)*scale+offset]))
    p.setPen(QColor('#234452')); p.drawText(35,790,'22 mm main body · 26 mm flange · 18 mm locating pilot · 20 mm overall height · separate STL halves + paired print plate')
    p.drawText(35,821,'Hardware and wiring omitted here. Print orientation needs slicer inspection for the 6.1 mm bore bridge. No physical fit has been verified.')
    p.end(); image.save(str(folder/'holder-preview.png'))
