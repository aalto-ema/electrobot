"""Live, native schematic of modular rack geometry and holder seating."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QPen,QFont
from PySide6.QtWidgets import QWidget


class RackDiagram(QWidget):
    def __init__(self):
        super().__init__(); self.settings=None; self.setMinimumSize(450,240)
    def set_settings(self,s): self.settings=s; self.update()
    def paintEvent(self,event):
        if self.settings is None: return
        s=self.settings; d=s.lattice_dimensions(); p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        factor=min(self.width()/1000,self.height()/320)
        p.translate((self.width()-1000*factor)/2,(self.height()-320*factor)/2); p.scale(factor,factor)
        p.fillRect(QRectF(0,0,1000,320),QColor('#f4f8fa')); font=QFont(); font.setPixelSize(13); p.setFont(font)
        def text(x,y,t): p.setPen(QColor('#234452')); p.drawText(QPointF(x,y),t)
        def rect(x,y,w,h,color): p.setPen(QPen(QColor('#506675'),1)); p.setBrush(QColor(color)); p.drawRect(QRectF(x,y,w,h))
        text(12,20,'HOLDER SEAT · side section (lattice concept)' if s.rack_design=='lattice' else 'HOLDER SEAT · select modular lattice to use this design')
        text(12,40,f'Body Ø{s.holder_diameter:g} × {s.holder_height:g}; flange Ø{s.holder_flange_diameter:g} × {s.holder_flange_thickness:g} mm')
        # Physical Z from bench; fit entire assembled electrode and holder into panel.
        total=d['seat_height']+s.holder_height+s.holder_flange_thickness
        scale=min(2.5,205/max(total,1)); cx=130; floor=255
        def level(z): return floor-z*scale
        off=d['peg_offset']*scale
        rect(cx-off-d['foot_radius']*scale,level(s.rack_foot_base),(2*d['peg_offset']+2*d['foot_radius'])*scale,s.rack_foot_base*scale,'#a8ded6')
        for sign in (-1,1):
            rect(cx+sign*off-s.rack_foot_column_diameter/2*scale,level(d['foot_height']),s.rack_foot_column_diameter*scale,(d['foot_height']-s.rack_foot_base)*scale,'#a8ded6')
            rect(cx+sign*off-s.rack_peg_diameter/2*scale,level(d['foot_height']+s.rack_peg_length),s.rack_peg_diameter*scale,s.rack_peg_length*scale,'#087f73')
        top=d['foot_height']+s.rack_deck_thickness
        for sign in (-1,1):
            x=cx-d['outer']*scale if sign<0 else cx+d['bore']*scale
            rect(x,level(top),(d['outer']-d['bore'])*scale,s.rack_deck_thickness*scale,'#c5dce8')
            x=cx-d['seat']*scale if sign<0 else cx+d['bore']*scale
            rect(x,level(top),(d['seat']-d['bore'])*scale,s.rack_seat_depth*scale,'#f4f8fa')
        seat=d['seat_height']; rodtop=seat+s.holder_rod_depth
        rect(cx-s.rod_diameter/2*scale,level(rodtop),s.rod_diameter*scale,(s.rack_hanging_length+s.holder_rod_depth)*scale,'#c6cbd0')
        rect(cx-s.rod_diameter/2*scale,level(s.rack_tip_clearance+4),s.rod_diameter*scale,4*scale,'#343b42')
        # Cutaway holder: two body walls with the connected roof/flange above them.
        bore=(s.rod_diameter+s.holder_rod_clearance)/2
        for sign in (-1,1):
            x=cx-s.holder_diameter/2*scale if sign<0 else cx+bore*scale
            rect(x,level(seat+s.holder_height),(s.holder_diameter/2-bore)*scale,s.holder_height*scale,'#d8d2ed')
        rect(cx-s.holder_flange_diameter/2*scale,level(seat+s.holder_height+s.holder_flange_thickness),s.holder_flange_diameter*scale,s.holder_flange_thickness*scale,'#d8d2ed')
        rect(cx-s.holder_pad_diameter/2*scale,level(total),s.holder_pad_diameter*scale,2,'#cf9652')
        text(205,80,'Grip body and top contact stay exposed')
        text(205,103,f'Exposed body: {s.holder_height-s.rack_seat_depth:g} mm')
        text(205,126,f'Recess Ø{s.holder_diameter+s.rack_holder_clearance:g} × {s.rack_seat_depth:g} mm')
        text(205,149,f'Deck thickness: {s.rack_deck_thickness:g} mm')
        text(205,172,f'Seat height: {d["seat_height"]:g} mm above bench')
        text(205,195,f'Free rod length: {s.rack_hanging_length:g} mm')
        text(205,218,f'Tip clearance: {s.rack_tip_clearance:g} mm')
        text(205,241,f'Foot pegs Ø{s.rack_peg_diameter:g}; fit +{s.rack_peg_clearance:g} mm')
        text(12,282,'Print top supports and fork feet separately. Peg fit is provisional; secure feet to bench.')
        text(12,304,'Seat height is a bench dimension. Teach robot grip Z after assembly. No automatic Z change.')
        from .lattice_rack import modules,module_frame
        groups=modules(s); positions=s.rack_export_positions(); colors=['#087f73','#635bce','#3285c8','#ad7335']
        xmin=min(x for x,y,z in positions)-d['outer']; xmax=max(x for x,y,z in positions)+d['outer']
        ymin=min(y for x,y,z in positions)-d['outer']; ymax=max(y for x,y,z in positions)+d['outer']
        k=min(410/max(xmax-xmin,1),205/max(ymax-ymin,1))
        def xy(x,y): return QPointF(575+(x-xmin)*k,260-(y-ymin)*k)
        text(565,20,'TOP VIEW · exact experiment XY coordinates')
        text(565,40,f'{len(positions)} seats · {len(groups)} modules · up to {s.rack_module_slots} slots/module')
        p.save(); p.setClipRect(QRectF(565,50,425,216))
        for n,m in enumerate(groups):
            import math
            _,angle,_=module_frame(m); dx=d['peg_offset']*math.cos(angle); dy=d['peg_offset']*math.sin(angle)
            color=QColor(colors[n%len(colors)]); p.setPen(QPen(color,max(1,s.rack_rib_width*k),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            for a,b in zip(m['positions'],m['positions'][1:]): p.drawLine(xy(*a[:2]),xy(*b[:2]))
            for i,(x,y,z) in enumerate(m['positions']):
                pos=xy(x,y); p.setPen(QPen(color,1)); p.setBrush(QColor('#e5eff2')); p.drawEllipse(pos,d['outer']*k,d['outer']*k)
                p.setBrush(QColor('#f4f8fa')); p.drawEllipse(pos,d['seat']*k,d['seat']*k)
                if i in m['supports']:
                    p.setPen(QPen(QColor('#087f73'),1)); p.setBrush(QColor('#087f73'))
                    for sign in (-1,1): p.drawEllipse(xy(x+sign*dx,y+sign*dy),2,2)
                text(pos.x()-4,pos.y()+4,str(m['slots'][i]))
        p.restore(); p.setBrush(Qt.BrushStyle.NoBrush)
        text(565,282,'Colours = separate top modules; green dots = foot pegs.')
        text(565,304,f'Minimum provisional spacing: {d["separation"]:g} mm. Finger clearance needs testing.')
        p.end()
