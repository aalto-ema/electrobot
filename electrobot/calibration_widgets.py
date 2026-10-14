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
        super().__init__(); self.workspace=workspace; self.settings=None; self.pose=None
        self.setMinimumHeight(410); self.setMinimumWidth(450)
    def set_settings(self,s):
        self.settings=s; self.envelope=None
        if s.workspace_map:
            from .workspace_map import Envelope
            try: self.envelope=Envelope(s.workspace_map)
            except (ValueError,KeyError,TypeError): pass
        self.update()
    def set_pose(self,pose): self.pose=dict(pose) if pose else None; self.update()
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
        if s.rack_layout=='radial':
            text(20,45,f'Arc r={s.rack_radius:g} mm; start {s.rack_start_angle:g}°; step {s.rack_angle_step:g}°')
        # Include limits, all displayed rack slots, stations and origin. Equal XY
        # scaling preserves distances and circle shape, even outside the bounds.
        points=rack_points(s)
        xs=[s.workspace_x_min,s.workspace_x_max,0,s.cell_x,s.rinse_x]+[x for _,x,_,_,_ in points]
        ys=[s.workspace_y_min,s.workspace_y_max,0,s.cell_y,s.rinse_y]+[y for _,_,y,_,_ in points]
        if self.workspace:
            xs += [-s.workspace_radius_max,s.workspace_radius_max]
            ys += [-s.workspace_radius_max,s.workspace_radius_max]
        if self.pose: xs.append(self.pose['x']); ys.append(self.pose['y'])
        xlo,xhi=min(xs),max(xs); ylo,yhi=min(ys),max(ys)
        scale=min(390/max(1,xhi-xlo),255/max(1,yhi-ylo))*.92
        xc,yc=(xlo+xhi)/2,(ylo+yhi)/2
        def xy(x,y): return QPointF(250+(x-xc)*scale,179-(y-yc)*scale)
        def map_color(x,y,default):
            if not getattr(self,'envelope',None): return default
            state=self.envelope.status(x,y,min(s.rack_z,s.cell_z,s.rinse_z),s.safe_z,s.tool_r)
            return '#0b9b82' if state is True else '#c34848' if state is False else '#8198a5'
        base=xy(0,0)
        if self.workspace:
            p.setPen(QPen(QColor('#c6d8e0'),1.5)); p.setBrush(QColor('#e3eff2'))
            r=s.workspace_radius_max*scale; p.drawEllipse(base,r,r)
            p.setBrush(QColor('#f4f8fa')); r=s.workspace_radius_min*scale; p.drawEllipse(base,r,r); p.setBrush(Qt.BrushStyle.NoBrush)
        if getattr(self,'envelope',None):
            env=self.envelope
            p.setPen(Qt.PenStyle.NoPen)
            for a,b in zip(env.xs,env.xs[1:]):
                for c,d in zip(env.ys,env.ys[1:]):
                    color=map_color((a+b)/2,(c+d)/2,'#8198a5')
                    fill=QColor(color); fill.setAlpha(45); p.setBrush(fill)
                    p.drawRect(QRectF(xy(a,d),xy(b,c)).normalized())
            p.setBrush(Qt.BrushStyle.NoBrush)
        a=xy(s.workspace_x_min,s.workspace_y_max); b=xy(s.workspace_x_max,s.workspace_y_min)
        p.setPen(QPen(QColor('#635bce'),1.5)); p.drawRect(QRectF(a,b).normalized())
        line(xy(xlo,0).x(),base.y(),xy(xhi,0).x(),base.y(),'#c6d8e0')
        line(base.x(),xy(0,ylo).y(),base.x(),xy(0,yhi).y(),'#c6d8e0')
        dot(base.x(),base.y(),'#8198a5',3); text(base.x()+5,base.y()-6,'0,0')
        text(433,310,'+X →'); text(20,60,'+Y ↑')
        for index,x,y,z,selected in points:
            pos=xy(x,y); dot(pos.x(),pos.y(),map_color(x,y,'#635bce') if selected else '#aebdca',2.5,selected)
        for x,y,color,label in ((s.cell_x,s.cell_y,'#0e9f92','Cell'),(s.rinse_x,s.rinse_y,'#3285c8','Rinse')):
            pos=xy(x,y); dot(pos.x(),pos.y(),map_color(x,y,color),5); text(pos.x()+8,pos.y()-8,label)
        if self.pose:
            pos=xy(self.pose['x'],self.pose['y']); dot(pos.x(),pos.y(),'#d97706',7,False); text(pos.x()+8,pos.y()+17,'Robot')
        if self.workspace:
            text(20,334,f'X [{s.workspace_x_min:g}, {s.workspace_x_max:g}]   Y [{s.workspace_y_min:g}, {s.workspace_y_max:g}] mm')
            text(20,356,f'Radius [{s.workspace_radius_min:g}, {s.workspace_radius_max:g}] mm from base')
            text(20,378,'Map: green support / red rejection / grey unknown' if s.workspace_map else 'Allowed XY = rectangle ∩ radial band')
            columns,rows,_=rack_layout(s)
            text(510,334,f'{s.rack_layout.title()} rack: {columns} slots/row × {rows}; pitch {s.rack_pitch:g} mm')
        else:
            columns,rows,_=rack_layout(s)
            text(20,334,f'{columns} columns × {rows} rows; pitch {s.rack_pitch:g} mm; order +X then +Y')
            text(20,356,f'Slot 1 ({s.rack_x:g}, {s.rack_y:g}); filled slots {s.first_electrode}–{min(100,s.first_electrode+s.electrodes-1)}')
            text(20,378,f'Cell ({s.cell_x:g}, {s.cell_y:g}); rinse ({s.rinse_x:g}, {s.rinse_y:g}) mm')
        # Side view: shared absolute-Z scale. Station columns are categorical;
        # their XY positions are represented in the top view.
        live_z=self.pose['z'] if self.pose else s.safe_z
        zlo=min(s.workspace_z_min,s.workspace_z_max,s.rack_z,s.cell_z,s.rinse_z,s.safe_z,live_z)
        zhi=max(s.workspace_z_min,s.workspace_z_max,s.rack_z,s.cell_z,s.rinse_z,s.safe_z,live_z)
        if zhi-zlo<50:
            middle=(zlo+zhi)/2; zlo,zhi=middle-25,middle+25
        def zy(z): return 300-(z-zlo)/max(1,zhi-zlo)*235
        line(540,zy(zlo),540,zy(zhi),'#8198a5')
        for z,name,color in ((s.workspace_z_max,'Z max','#635bce'),(s.workspace_z_min,'Z min','#635bce'),(s.safe_z,'Travel Z','#0e9f92')):
            y=zy(z); line(540,y,940,y,color,name=='Travel Z'); text(800 if name.startswith('Z ') else 550,y-5,f'{name} {z:g} mm')
        for x,z,label in ((635,s.rack_z,'Rack grip'),(760,s.cell_z,'Cell seat'),(885,s.rinse_z,'Rinse dip')):
            line(x,zy(s.safe_z),x,zy(z)); dot(x,zy(z)); text(x-37,zy(z)+18,label); text(x-30,zy(z)+35,f'Z={z:g}')
        if self.pose:
            y=zy(live_z); line(540,y,940,y,'#d97706',True); text(700,y-6,f'Robot Z {live_z:g}')
        text(510,356,f'Tool R {s.tool_r:g}° about vertical Z; no tilt')
        text(510,378,'Lift → transfer at Travel Z → lower')
        text(20,400,'Distances plotted to scale; labels may overlap for nearby stations. Tool coordinates, not electrode tip depth. No collision model.')
        p.end()


class RobotTracker(QWidget):
    """Compact XY/XZ live tool feedback, shared by experiment and manual pages."""
    def __init__(self):
        super().__init__(); self.settings=None; self.pose=None; self.trail=[]
        self.setMinimumSize(240,260)
    def set_settings(self,s): self.settings=s; self.update()
    def set_pose(self,pose):
        self.pose=dict(pose) if pose else None
        if pose and (not self.trail or self.trail[-1]!=self.pose):
            self.trail.append(dict(pose)); self.trail=self.trail[-150:]
        if not pose: self.trail=[]
        self.update()
    def clear_trail(self): self.trail=[]; self.update()
    def paintEvent(self,event):
        if self.settings is None: return
        s=self.settings; p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); p.fillRect(self.rect(),QColor('#f4f8fa'))
        def text(x,y,t): p.setPen(QColor('#234452')); p.drawText(QPointF(x,y),t)
        text(10,19,'Robot position · '+('simulated' if s.mode=='simulation' else 'reported'))
        text(10,38,'Orange: robot   Grey: recent path')
        if self.pose:
            text(10,h-31,f"X {self.pose['x']:.1f}  Y {self.pose['y']:.1f} mm")
            text(10,h-12,f"Z {self.pose['z']:.1f} mm  R {self.pose['r']:.1f}°")
        else: text(10,h-15,'Position unavailable · connect robot')
        stations=[(x,y,z,'#635bce','') for _,x,y,z,selected in rack_points(s) if selected]
        stations.extend(((s.cell_x,s.cell_y,s.cell_z,'#0e9f92','C'),(s.rinse_x,s.rinse_y,s.rinse_z,'#3285c8','R')))
        poses=self.trail+([self.pose] if self.pose else [])
        panel_height=max(28,(h-142)/2)
        for n,axis in enumerate(('y','z')):
            r=QRectF(20,62+n*(panel_height+26),w-40,panel_height)
            text(10,r.top()-4,'XY · top view' if axis=='y' else 'XZ · side view')
            coords=[(x,y if axis=='y' else z) for x,y,z,_,_ in stations]+[(v['x'],v[axis]) for v in poses]
            if not coords: continue
            xmin,xmax=min(v[0] for v in coords),max(v[0] for v in coords)
            ymin,ymax=min(v[1] for v in coords),max(v[1] for v in coords)
            spanx=max(40,xmax-xmin+20); spany=max(40,ymax-ymin+20)
            scale=min(max(1,r.width()-24)/spanx,max(1,r.height()-20)/spany)
            def xy(x,y): return QPointF(r.center().x()+(x-(xmin+xmax)/2)*scale,r.center().y()-(y-(ymin+ymax)/2)*scale)
            p.setPen(QPen(QColor('#d6e0e5'),1)); p.drawRect(r)
            p.save(); p.setClipRect(r)
            if axis=='z':
                p.setPen(QPen(QColor('#0e9f92'),1,Qt.PenStyle.DashLine))
                p.drawLine(xy(xmin,s.safe_z),xy(xmax,s.safe_z))
            p.setPen(QPen(QColor('#b4c1cb'),1))
            for a,b in zip(poses,poses[1:]): p.drawLine(xy(a['x'],a[axis]),xy(b['x'],b[axis]))
            for x,y,z,color,label in stations:
                pos=xy(x,y if axis=='y' else z); p.setPen(QPen(QColor(color),1)); p.setBrush(QColor(color)); p.drawEllipse(pos,3,3)
                if label: text(pos.x()+5,pos.y()-5,label)
            if self.pose:
                pos=xy(self.pose['x'],self.pose[axis]); p.setPen(QPen(QColor('#d97706'),2)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pos,6,6); p.drawLine(pos+QPointF(-9,0),pos+QPointF(9,0)); p.drawLine(pos+QPointF(0,-9),pos+QPointF(0,9))
            p.restore(); p.setBrush(Qt.BrushStyle.NoBrush)
        p.end()
