"""Native calibration views plotted in robot coordinates; no collision model."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget


def rack_layout(s):
    """Full rows through last selected slot in actual robot slot order."""
    last=min(100,s.first_electrode+s.electrodes-1)
    columns=max(1,s.rack_columns); rows=(last+columns-1)//columns
    return columns,rows,[(i,(i-1)%columns,(i-1)//columns,s.first_electrode<=i<=last)
                         for i in range(1,min(100,columns*rows)+1)]


def rack_points(s):
    return [(i,*s.rack_pose(i),selected) for i,_,_,selected in rack_layout(s)[2]]


class CalibrationDiagram(QWidget):
    def __init__(self,workspace=False):
        super().__init__(); self.workspace=workspace; self.settings=None
        self.setMinimumHeight(410); self.setMinimumWidth(450)
    def set_settings(self,s): self.settings=s; self.update()
    def paintEvent(self,event):
        if self.settings is None: return
        s=self.settings; p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        factor=min(self.width()/960,self.height()/410)
        p.translate((self.width()-960*factor)/2,(self.height()-410*factor)/2)
        p.scale(factor,factor)
        p.fillRect(QRectF(0,0,960,410),QColor('#f4f8fa'))
        def text(x,y,t):
            p.setPen(QColor('#234452')); p.drawText(QPointF(x,y),t)
        def line(x,y,a,b,color='#0e9f92',dash=False):
            p.setPen(QPen(QColor(color),1.5,Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine)); p.drawLine(QPointF(x,y),QPointF(a,b))
        def dot(x,y,color='#0e9f92',radius=4,filled=True):
            p.setPen(QPen(QColor(color),1.5)); p.setBrush(QColor(color) if filled else Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x,y),radius,radius); p.setBrush(Qt.BrushStyle.NoBrush)
        text(20,25,'TOP VIEW · actual robot XY coordinates'); text(510,25,'SIDE VIEW · actual Z heights')
        # Include limits, all displayed rack slots, stations and origin. Equal XY
        # scaling preserves distances and circle shape, even outside the bounds.
        points=rack_points(s)
        xs=[s.workspace_x_min,s.workspace_x_max,0,s.cell_x,s.rinse_x]+[x for _,x,_,_,_ in points]
        ys=[s.workspace_y_min,s.workspace_y_max,0,s.cell_y,s.rinse_y]+[y for _,_,y,_,_ in points]
        if self.workspace:
            xs += [-s.workspace_radius_max,s.workspace_radius_max]
            ys += [-s.workspace_radius_max,s.workspace_radius_max]
        xlo,xhi=min(xs),max(xs); ylo,yhi=min(ys),max(ys)
        scale=min(390/max(1,xhi-xlo),255/max(1,yhi-ylo))*.92
        xc,yc=(xlo+xhi)/2,(ylo+yhi)/2
        def xy(x,y): return QPointF(250+(x-xc)*scale,179-(y-yc)*scale)
        base=xy(0,0)
        if self.workspace:
            p.setPen(QPen(QColor('#c6d8e0'),1.5)); p.setBrush(QColor('#e3eff2'))
            r=s.workspace_radius_max*scale; p.drawEllipse(base,r,r)
            p.setBrush(QColor('#f4f8fa')); r=s.workspace_radius_min*scale; p.drawEllipse(base,r,r); p.setBrush(Qt.BrushStyle.NoBrush)
        a=xy(s.workspace_x_min,s.workspace_y_max); b=xy(s.workspace_x_max,s.workspace_y_min)
        p.setPen(QPen(QColor('#635bce'),1.5)); p.drawRect(QRectF(a,b).normalized())
        line(xy(xlo,0).x(),base.y(),xy(xhi,0).x(),base.y(),'#c6d8e0')
        line(base.x(),xy(0,ylo).y(),base.x(),xy(0,yhi).y(),'#c6d8e0')
        dot(base.x(),base.y(),'#8198a5',3); text(base.x()+5,base.y()-6,'0,0')
        text(433,310,'+X →'); text(20,60,'+Y ↑')
        for index,x,y,z,selected in points:
            pos=xy(x,y); dot(pos.x(),pos.y(),'#635bce' if selected else '#aebdca',2.5,selected)
        for x,y,color,label in ((s.cell_x,s.cell_y,'#0e9f92','Cell'),(s.rinse_x,s.rinse_y,'#3285c8','Rinse')):
            pos=xy(x,y); dot(pos.x(),pos.y(),color,5); text(pos.x()+8,pos.y()-8,label)
        if self.workspace:
            text(20,334,f'X [{s.workspace_x_min:g}, {s.workspace_x_max:g}]   Y [{s.workspace_y_min:g}, {s.workspace_y_max:g}] mm')
            text(20,356,f'Radius [{s.workspace_radius_min:g}, {s.workspace_radius_max:g}] mm from base')
            text(20,378,'Allowed XY = rectangle ∩ radial band')
        else:
            columns,rows,_=rack_layout(s)
            text(20,334,f'{columns} columns × {rows} rows; pitch {s.rack_pitch:g} mm; order +X then +Y')
            text(20,356,f'Slot 1 ({s.rack_x:g}, {s.rack_y:g}); filled slots {s.first_electrode}–{min(100,s.first_electrode+s.electrodes-1)}')
            text(20,378,f'Cell ({s.cell_x:g}, {s.cell_y:g}); rinse ({s.rinse_x:g}, {s.rinse_y:g}) mm')
        # Side view: shared absolute-Z scale. Station columns are categorical;
        # their XY positions are represented in the top view.
        zlo=min(s.workspace_z_min,s.workspace_z_max,s.rack_z,s.cell_z,s.rinse_z,s.safe_z)
        zhi=max(s.workspace_z_min,s.workspace_z_max,s.rack_z,s.cell_z,s.rinse_z,s.safe_z)
        def zy(z): return 300-(z-zlo)/max(1,zhi-zlo)*235
        line(540,zy(zlo),540,zy(zhi),'#8198a5')
        for z,name,color in ((s.workspace_z_max,'Z max','#635bce'),(s.workspace_z_min,'Z min','#635bce'),(s.safe_z,'Travel Z','#0e9f92')):
            y=zy(z); line(540,y,940,y,color,name=='Travel Z'); text(550,y-5,f'{name} {z:g} mm')
        for x,z,label in ((635,s.rack_z,'Rack grip'),(760,s.cell_z,'Cell seat'),(885,s.rinse_z,'Rinse dip')):
            line(x,zy(s.safe_z),x,zy(z)); dot(x,zy(z)); text(x-37,zy(z)+18,label); text(x-30,zy(z)+35,f'Z={z:g}')
        text(510,356,f'Tool R {s.tool_r:g}° about vertical Z; no tilt')
        text(510,378,'Lift → transfer at Travel Z → lower')
        text(20,400,'Distances plotted to scale; labels may overlap for nearby stations. Tool coordinates, not electrode tip depth. No collision model.')
        p.end()
