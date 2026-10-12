"""Native, resizable calibration diagrams. Schematics are not collision models."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget


class CalibrationDiagram(QWidget):
    def __init__(self,workspace=False):
        super().__init__(); self.workspace=workspace; self.settings=None
        self.setMinimumHeight(330); self.setMinimumWidth(450)
    def set_settings(self,s):
        self.settings=s; self.update()
    def paintEvent(self,event):
        if self.settings is None: return
        s=self.settings; p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width()/960,self.height()/330)
        p.fillRect(QRectF(0,0,960,330),QColor('#f4f8fa'))
        def text(x,y,t):
            p.setPen(QColor('#234452')); p.drawText(QPointF(x,y),t)
        def line(x,y,a,b,color='#0e9f92',dash=False):
            p.setPen(QPen(QColor(color),2,Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine)); p.drawLine(QPointF(x,y),QPointF(a,b))
        def dot(x,y,color='#0e9f92'):
            p.setPen(QPen(QColor(color),2)); p.setBrush(QColor(color)); p.drawEllipse(QPointF(x,y),5,5); p.setBrush(Qt.BrushStyle.NoBrush)
        if self.workspace:
            text(20,25,'TOP VIEW · XY rectangle ∩ radial band'); text(510,25,'SIDE VIEW · Z limits')
            p.setPen(QPen(QColor('#c6d8e0'),2)); p.setBrush(QColor('#e3eff2'))
            p.drawEllipse(QPointF(220,173),119,119); p.setBrush(QColor('#f4f8fa')); p.drawEllipse(QPointF(220,173),48,48); p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#635bce'),2)); p.drawRect(QRectF(100,72,230,202))
            dot(220,173); text(230,170,'Base (0,0)')
            line(220,173,294,82); text(338,88,f'Radius max {s.workspace_radius_max:g} mm')
            line(220,173,250,135); text(338,137,f'Radius min {s.workspace_radius_min:g} mm')
            text(20,62,f'Y max {s.workspace_y_max:g}'); text(20,291,f'Y min {s.workspace_y_min:g}')
            text(97,310,f'X min {s.workspace_x_min:g}'); text(272,310,f'X max {s.workspace_x_max:g}')
            line(565,275,565, 60,'#635bce'); text(575,64,f'Z max {s.workspace_z_max:g} mm')
            line(560,270,920,270,'#635bce'); text(575,290,f'Z min {s.workspace_z_min:g} mm')
            line(560,113,920,113,dash=True); text(575,106,f'Travel Z {s.safe_z:g} mm')
            for x,z,name in ((630,s.rack_z,'Rack'),(725,s.cell_z,'Cell'),(830,s.rinse_z,'Rinse')):
                dot(x,195); line(x,113,x,195); text(x-20,218,name); text(x-20,237,f'Z={z:g}')
            text(510,320,'Schematic · endpoints must pass BOTH XY/radius and Z limits')
        else:
            text(20,25,'TOP VIEW · rack and station positions'); text(510,25,'SIDE VIEW · approach and transfer heights')
            line(35,267,470,267,'#8198a5'); line(35,267,35,55,'#8198a5')
            text(455,288,'+X'); text(42,55,'+Y')
            for row in range(2):
                for col in range(4):
                    dot(95+col*45,215-row*45,'#635bce')
            text(70,245,f'Slot 1: X={s.rack_x:g}, Y={s.rack_y:g} mm')
            line(95,155,140,155); text(67,142,f'Slot pitch {s.rack_pitch:g} mm')
            text(67,105,f'{s.rack_columns} columns; slots increase along +X, then +Y')
            dot(335,165); text(300,146,f'Cell ({s.cell_x:g}, {s.cell_y:g})')
            dot(405,80,'#3285c8'); text(320,62,f'Rinse ({s.rinse_x:g}, {s.rinse_y:g})')
            text(20,313,'Tool R rotates about vertical Z (±90°); not tilt')
            line(535, 80,920,80,dash=True); text(545,65,f'Travel Z = {s.safe_z:g} mm')
            for x,z,name in ((590,s.rack_z,'Rack grip'),(720,s.cell_z,'Cell seat'),(850,s.rinse_z,'Rinse dip')):
                line(x,80,x,230); dot(x,230); text(x-40,254,name); text(x-35,273,f'Z={z:g} mm')
            line(590,80,850,80); text(630,113,'1. Lift → 2. Transfer → 3. Lower')
            text(530,156,f'Tool R = {s.tool_r:g}° at every station')
            text(510,313,'Schematic · values are robot tool coordinates, not tip depth')
        p.end()
