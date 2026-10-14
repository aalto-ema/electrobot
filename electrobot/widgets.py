from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QPushButton, QGroupBox, QVBoxLayout
COLORS=['#0e9f92','#635bce','#d58a24','#ce5275','#3285c8']
class Plot(QWidget):
    def __init__(self):
        super().__init__(); self.setMinimumHeight(285); self.data={}; self.selected=None; self.synthetic=True; self.strides={}; self.counts={}; self.latest={}; self.dirty=True
    def clear(self):
        self.data={}; self.strides={}; self.counts={}; self.latest={}; self.dirty=True; self.update()
    def add(self,index,t,e,i):
        values=self.data.setdefault(index,[]); stride=self.strides.setdefault(index,1)
        count=self.counts.get(index,0)+1; self.counts[index]=count; self.latest[index]=(e,i)
        if count % stride==0: values.append((e,i))
        if len(values)>4000:
            self.data[index]=values[::2]; self.strides[index]=stride*2
        self.dirty=True
    def paintEvent(self,event):
        self.dirty=False
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(65,35,max(20,self.width()-95),max(20,self.height()-85))
        allpoints=[v for values in self.data.values() for v in values]
        lo=min([v[0] for v in allpoints]+[-.5]); hi=max([v[0] for v in allpoints]+[.5])
        imax=(max([abs(v[1]) for v in allpoints]+[.001]) if allpoints else 60)*1.1
        p.setPen(QColor('#8b99a7'))
        for k in range(5):
            y=r.top()+k*r.height()/4
            p.setPen(QPen(QColor('#e7edf2'),1)); p.drawLine(QPointF(r.left(),y),QPointF(r.right(),y))
            p.setPen(QColor('#728191')); p.drawText(QRectF(0,y-9,55,18),Qt.AlignmentFlag.AlignRight,f'{imax-k*imax/2:.3g}')
            x=r.left()+k*r.width()/4
            p.drawText(QRectF(x-30,r.bottom()+8,60,20),Qt.AlignmentFlag.AlignCenter,f'{lo+k*(hi-lo)/4:.2f}')
        p.drawText(12,20,'Current (µA)' + (' · synthetic' if self.synthetic else ' · measured')); p.drawText(int(r.center().x()-45),self.height()-7,'Potential (V)')
        for index,values in self.data.items():
            if self.selected is not None and index!=self.selected: continue
            path=QPainterPath()
            display=values[::max(1,len(values)//1200)] + ([self.latest[index]] if index in self.latest else [])
            for n,(e,i) in enumerate(display):
                xy=QPointF(r.left()+(e-lo)/(hi-lo)*r.width(),r.center().y()-i/imax*r.height()/2)
                path.moveTo(xy) if n==0 else path.lineTo(xy)
            p.setPen(QPen(QColor(COLORS[(index-1)%len(COLORS)]),2)); p.drawPath(path)
        if not allpoints:
            p.setPen(QColor('#8b99a7')); p.drawText(r,Qt.AlignmentFlag.AlignCenter,'Start a run to see the CV curves')

class CameraPreview(QWidget):
    def __init__(self):
        super().__init__(); self.image=None; self.setMinimumSize(260,90)
    def set_frame(self,image): self.image=image; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip=QPainterPath(); clip.addRoundedRect(QRectF(self.rect()),8,8); p.setClipPath(clip)
        p.fillRect(self.rect(),QColor('#152f3c'))
        if self.image is not None:
            size=self.image.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
            r=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height())
            p.drawImage(r,self.image)
        else:
            p.setPen(QColor('#a8bec9')); p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'No camera connected\nLive preview will appear here')

class CapSketch(QWidget):
    def __init__(self,s):
        super().__init__(); self.s=s; self.setMinimumHeight(300)
    def paintEvent(self,event):
        s=self.s; p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d=s.rim_diameter+s.cap_clearance+2*s.cap_wall
        scale=min((self.width()-110)/d,(self.height()-90)/d)
        cx=self.width()/2; cy=self.height()/2
        def circle(x,y,diameter,fill):
            p.setBrush(QColor(fill)); p.setPen(QPen(QColor('#2f6073'),1.5))
            p.drawEllipse(QPointF(cx+x*scale,cy+y*scale),diameter*scale/2,diameter*scale/2)
        circle(0,0,d,'#d8efeb'); circle(0,0,s.rim_diameter+s.cap_clearance,'#eef8f6')
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor('#95b8b2'),1,Qt.PenStyle.DashLine))
        p.drawEllipse(QPointF(cx,cy),s.beaker_diameter*scale/2,s.beaker_diameter*scale/2)
        circle(0,0,s.funnel_diameter,'#b4d9d1'); circle(0,0,s.rod_diameter+s.we_clearance,'white')
        circle(-s.port_offset,0,s.re_hole,'white'); circle(s.port_offset,0,s.ce_hole,'white')
        p.setPen(QColor('#163c4b'))
        for x,text in ((-s.port_offset,'RE'),(0,'WE'),(s.port_offset,'CE')):
            p.drawText(QRectF(cx+x*scale-25,cy+27,50,25),Qt.AlignmentFlag.AlignCenter,text)
        p.fillRect(QRectF(cx-6*scale,cy-d*scale/2,12*scale,s.cap_wall*scale+2*scale),QColor('#f7fafc'))
        p.drawText(QRectF(0,10,self.width(),30),Qt.AlignmentFlag.AlignCenter,f'Top view · Ø {d:.1f} mm · not to scale')
        p.drawText(QRectF(0,self.height()-35,self.width(),25),Qt.AlignmentFlag.AlignCenter,'Spout notch / vent at top · dry WE contact still to be designed')

def button(text,callback,primary=False):
    b=QPushButton(text); b.clicked.connect(callback)
    if primary: b.setObjectName('primary')
    return b

def card(title):
    w=QGroupBox(title); layout=QVBoxLayout(w); layout.setContentsMargins(18,24,18,18)
    return w,layout

STYLE='''
QWidget { font-family: "Inter", "Segoe UI", "Helvetica Neue"; font-size: 13px; color:#243c4b; background:#f7fafc; }
QWidget#sidebar { background:#142f3d; }
#sidebar QLabel { background:transparent; color:#b0c6d1; }
#brand { font-size:29px; font-weight:700; color:white; }
#navsub { font-size:10px; line-height:150%; }
QListWidget { background:transparent; border:none; outline:none; color:#b8ced8; }
QListWidget::item { padding:15px 10px; margin:3px 0; border-radius:7px; }
QListWidget::item:selected { background:#265060; color:white; }
#heading { font-size:26px; font-weight:650; }
#badge { color:#087c70; background:#ddf1eb; border-radius:12px; padding:8px 13px; font-size:11px; font-weight:700; }
QGroupBox { background:white; border:1px solid #dee7ed; border-radius:10px; font-weight:600; margin-top:12px; }
QGroupBox::title { subcontrol-origin:margin; left:18px; padding:0 5px; }
QGroupBox QWidget { background:white; }
#note { color:#647988; font-weight:400; line-height:150%; }
#metric { font-size:21px; font-weight:600; }
QPushButton { background:white; border:1px solid #cfdae2; border-radius:7px; padding:10px 17px; font-weight:600; }
QPushButton:hover { background:#eaf4f3; border-color:#69b0a7; }
QPushButton#primary { background:#0d8a7d; color:white; border-color:#0d8a7d; }
QPushButton#primary:hover { background:#08776c; }
QPushButton#danger { color:#b54747; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled { background:#eef2f5; color:#a4b1ba; border-color:#e0e6eb; }
QSpinBox,QDoubleSpinBox,QLineEdit,QComboBox { border:1px solid #cad7df; border-radius:5px; padding:7px; background:white; selection-background-color:#0d8a7d; }
QSpinBox:focus,QDoubleSpinBox:focus,QLineEdit:focus,QComboBox:focus { border:1px solid #0d8a7d; }
QProgressBar { border:none; background:#e9eff3; border-radius:5px; height:20px; text-align:center; }
QProgressBar::chunk { background:#0d9b8d; border-radius:5px; }
QPlainTextEdit { border:none; color:#647988; font-family:"Menlo","Consolas"; font-size:11px; }
QScrollArea { border:none; }
#preview { background:#152f3c; color:#a8bec9; border-radius:10px; }
QStatusBar { color:#647988; background:#edf3f6; }
'''
