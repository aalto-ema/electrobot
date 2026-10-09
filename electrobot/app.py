import json
import sys
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import Qt, QThread, Signal, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPixmap, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QLabel,QPushButton,
    QVBoxLayout,QHBoxLayout,QGridLayout,QListWidget,QStackedWidget,QGroupBox,
    QFormLayout,QDoubleSpinBox,QSpinBox,QLineEdit,QComboBox,QScrollArea,
    QProgressBar,QPlainTextEdit,QFileDialog,QMessageBox,QSplitter)
from .config import Settings
from .engine import Experiment,Control
from .camera import CameraWorker

ROOT=Path(__file__).resolve().parent.parent
COLORS=['#0e9f92','#635bce','#d58a24','#ce5275','#3285c8']

class RunWorker(QThread):
    event=Signal(dict); point=Signal(int,float,float,float); result=Signal(str,str)
    def __init__(self,s):
        super().__init__(); self.s=s; self.control=Control()
    def run(self):
        try:
            folder,status=Experiment(self.s,self.control,self.event.emit,self.point.emit,ROOT/'runs').run()
            self.result.emit(str(folder),status)
        except Exception as exc: self.result.emit('',f'failed: {exc}')

class Plot(QWidget):
    def __init__(self):
        super().__init__(); self.setMinimumHeight(285); self.data={}; self.selected=None
    def add(self,index,t,e,i):
        self.data.setdefault(index,[]).append((e,i))
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(65,35,max(20,self.width()-95),max(20,self.height()-85))
        allpoints=[v for values in self.data.values() for v in values]
        lo=min([v[0] for v in allpoints]+[-.5]); hi=max([v[0] for v in allpoints]+[.5])
        imax=max([abs(v[1]) for v in allpoints]+[60])*1.1
        p.setPen(QColor('#8b99a7'))
        for k in range(5):
            y=r.top()+k*r.height()/4
            p.setPen(QPen(QColor('#e7edf2'),1)); p.drawLine(QPointF(r.left(),y),QPointF(r.right(),y))
            p.setPen(QColor('#728191')); p.drawText(QRectF(0,y-9,55,18),Qt.AlignmentFlag.AlignRight,f'{imax-k*imax/2:.0f}')
            x=r.left()+k*r.width()/4
            p.drawText(QRectF(x-30,r.bottom()+8,60,20),Qt.AlignmentFlag.AlignCenter,f'{lo+k*(hi-lo)/4:.2f}')
        p.drawText(12,20,'Current (µA) · synthetic'); p.drawText(int(r.center().x()-45),self.height()-7,'Potential (V)')
        for index,values in self.data.items():
            if self.selected is not None and index!=self.selected: continue
            path=QPainterPath()
            for n,(e,i) in enumerate(values):
                xy=QPointF(r.left()+(e-lo)/(hi-lo)*r.width(),r.center().y()-i/imax*r.height()/2)
                path.moveTo(xy) if n==0 else path.lineTo(xy)
            p.setPen(QPen(QColor(COLORS[(index-1)%len(COLORS)]),2)); p.drawPath(path)
        if not allpoints:
            p.setPen(QColor('#8b99a7')); p.drawText(r,Qt.AlignmentFlag.AlignCenter,'Start a simulated run to see the CV curves')

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

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Electrobot · Electrochemistry Workbench'); self.resize(1280,900)
        self.s=Settings(); self.fields={}; self.worker=None; self.camera=None; self.last_frame=None; self.output=None
        self.paused=False; self._close_pending=False
        if (ROOT/'settings.json').exists():
            try: self.s=Settings(**json.loads((ROOT/'settings.json').read_text())).validate()
            except Exception: pass
        base=QWidget(); self.setCentralWidget(base); shell=QHBoxLayout(base); shell.setContentsMargins(0,0,0,0); shell.setSpacing(0)
        sidebar=QWidget(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(220); navlayout=QVBoxLayout(sidebar)
        navlayout.setContentsMargins(22,30,22,24)
        brand=QLabel('electrobot'); brand.setObjectName('brand'); navlayout.addWidget(brand)
        sub=QLabel('ELECTROCHEMISTRY\nWORKBENCH'); sub.setObjectName('navsub'); navlayout.addWidget(sub); navlayout.addSpacing(35)
        self.nav=QListWidget(); self.nav.addItems(['Run dashboard','Experiment settings','Cell & carrier','Robot & rack','Camera']); navlayout.addWidget(self.nav)
        footer=QLabel('SIMULATION MODE\nHardware integration pending'); footer.setObjectName('navsub'); footer.setWordWrap(True); navlayout.addWidget(footer)
        shell.addWidget(sidebar); content=QWidget(); main=QVBoxLayout(content); main.setContentsMargins(30,24,30,24); main.setSpacing(18)
        header=QHBoxLayout(); self.heading=QLabel('Run dashboard'); self.heading.setObjectName('heading'); header.addWidget(self.heading); header.addStretch()
        badge=QLabel('●  SIMULATION'); badge.setObjectName('badge'); header.addWidget(badge); main.addLayout(header)
        self.pages=QStackedWidget(); main.addWidget(self.pages); shell.addWidget(content)
        self.make_dashboard(); self.make_experiment(); self.make_cell(); self.make_robot(); self.make_camera()
        self.nav.currentRowChanged.connect(self.change_page); self.nav.setCurrentRow(0)
        self.timer=QTimer(self); self.timer.timeout.connect(self.plot.update); self.timer.start(100)
        self.statusBar().showMessage('Ready · All robot and measurement operations are simulated')

    def change_page(self,index):
        self.pages.setCurrentIndex(index); self.heading.setText(self.nav.item(index).text())
    def page(self,scroll=False):
        w=QWidget(); layout=QVBoxLayout(w); layout.setSpacing(18)
        if scroll:
            wrapper=QScrollArea(); wrapper.setWidgetResizable(True); wrapper.setWidget(w); self.pages.addWidget(wrapper)
        else: self.pages.addWidget(w)
        return w,layout
    def note(self,text):
        l=QLabel(text); l.setWordWrap(True); l.setObjectName('note'); return l
    def field(self,form,key,label,minimum=None,maximum=None):
        value=getattr(self.s,key)
        if isinstance(value,int):
            f=QSpinBox(); f.setRange(int(minimum if minimum is not None else 1),int(maximum or 100)); f.setValue(value)
        elif isinstance(value,float):
            f=QDoubleSpinBox(); f.setDecimals(4 if key in ('step_v','scan_rate') else 2)
            f.setRange(minimum if minimum is not None else 0.01,maximum or 10000); f.setValue(value)
            f.setSingleStep(.01 if key.endswith('_v') or key=='scan_rate' else 1)
        else: f=QLineEdit(value)
        self.fields[key]=f; form.addRow(label,f); f.setMinimumWidth(155)
        return f
    def settings_group(self,title,items):
        g=QGroupBox(title); form=QFormLayout(g); form.setContentsMargins(18,24,18,18); form.setVerticalSpacing(12)
        for item in items: self.field(form,*item)
        return g
    def configuration_actions(self,layout):
        actions=QHBoxLayout(); actions.addWidget(button('Save configuration',self.save,True)); actions.addWidget(button('Load configuration…',self.load)); actions.addStretch(); layout.addLayout(actions)
    def save(self):
        try:
            self.s=self.read_settings(); (ROOT/'settings.json').write_text(json.dumps(asdict(self.s),indent=2))
            self.sketch.s=self.s; self.sketch.update(); self.statusBar().showMessage('Configuration saved')
        except Exception as exc: QMessageBox.warning(self,'Check configuration',str(exc))
    def load(self):
        name,_=QFileDialog.getOpenFileName(self,'Load configuration',str(ROOT),'JSON (*.json)')
        if not name: return
        try:
            s=Settings(**json.loads(Path(name).read_text())).validate()
            for key,f in self.fields.items():
                if isinstance(f,QComboBox): f.setCurrentIndex(f.findData(getattr(s,key)))
                elif isinstance(f,(QSpinBox,QDoubleSpinBox)): f.setValue(getattr(s,key))
                else: f.setText(getattr(s,key))
            self.s=s; self.sketch.s=s; self.sketch.update()
        except Exception as exc: QMessageBox.warning(self,'Cannot load configuration',str(exc))

    def make_dashboard(self):
        w,l=self.page(); l.addWidget(self.note('Develop and test the complete sequence here. CV data is synthetic; no robot or potentiostat commands are sent.'))
        actions=QHBoxLayout(); self.start=button('▶  Start simulated batch',self.start_run,True); self.pause=button('Pause',self.pause_run); self.stop=button('Stop',self.stop_run)
        self.pause.setEnabled(False); self.stop.setEnabled(False); self.stop.setObjectName('danger')
        actions.addWidget(self.start); actions.addWidget(self.pause); actions.addWidget(self.stop); actions.addStretch(); actions.addWidget(button('Open run folder',self.open_output)); l.addLayout(actions)
        top=QHBoxLayout(); a,al=card('Batch progress'); self.state=QLabel('Ready to run'); self.state.setObjectName('metric'); al.addWidget(self.state)
        self.progress=QProgressBar(); self.progress.setRange(0,self.s.electrodes); self.progress.setValue(0); al.addWidget(self.progress); top.addWidget(a,2)
        b,bl=card('Sequence'); bl.addWidget(self.note('Pickup → seat → measure → retrieve\nRinse → return to original slot')); top.addWidget(b,3); l.addLayout(top)
        p,pl=card('Cyclic voltammetry'); self.plot=Plot()
        plottools=QHBoxLayout(); plottools.addWidget(QLabel('Display')); self.plot_selection=QComboBox(); self.plot_selection.addItem('All electrodes',None)
        self.plot_selection.currentIndexChanged.connect(self.select_plot); plottools.addWidget(self.plot_selection); plottools.addStretch(); pl.addLayout(plottools)
        pl.addWidget(self.plot); l.addWidget(p,3)
        e,el=card('Activity'); self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(2000); self.log.setMaximumHeight(145); el.addWidget(self.log); l.addWidget(e,1)
    def make_experiment(self):
        w,l=self.page(True); l.addWidget(self.note('Potentials are relative to the selected reference electrode. These defaults are for simulation; choose a chemistry-appropriate window before hardware use.'))
        row=QHBoxLayout(); row.addWidget(self.settings_group('Cyclic voltammetry',[
            ('start_v','Start potential (V)',-3,3),('vertex1_v','Upper vertex (V)',-3,3),
            ('vertex2_v','Lower vertex (V)',-3,3),('end_v','End potential (V)',-3,3),
            ('scan_rate','Scan rate (V/s)',.0001,10),('step_v','Potential step (V)',.0001,1),('cycles','Cycles',1,100),
            ('reference_label','Reference electrode')]))
        g=QGroupBox('Batch & measurement'); f=QFormLayout(g); f.setContentsMargins(18,24,18,18)
        self.field(f,'electrodes','Number of electrodes',1,100); self.field(f,'settle','Settling time (s)',0,600)
        cr=QComboBox()
        for v in (.001,.01,.1,1,10,100,1000,10000): cr.addItem(f'{v:g} µA',v)
        cr.setCurrentIndex(cr.findData(self.s.current_range_ua)); self.fields['current_range_ua']=cr
        f.addRow('Current range',cr)
        self.field(f,'simulation_speed','Simulation speed multiplier',.1,100)
        row.addWidget(g); l.addLayout(row)
        l.addWidget(self.settings_group('Rinse', [('rinse_dips','Number of dips',1,20),('rinse_dwell','Dwell per dip (s)',0,120)]))
        self.configuration_actions(l); l.addStretch()
    def make_cell(self):
        w,l=self.page(True); l.addWidget(self.note('Nominal 100 mL low-form beaker: body Ø50 × 70 mm. Rim Ø53 mm is an unmeasured placeholder. The cap is a removable, vented fit prototype.'))
        row=QHBoxLayout(); row.addWidget(self.settings_group('Beaker & cap (mm)',[
            ('beaker_diameter','Beaker body diameter'),('beaker_height','Beaker height'),('rim_diameter','Measured rim diameter'),
            ('cap_clearance','Diametral rim clearance'),('cap_wall','Skirt wall thickness'),('cap_thickness','Cap plate thickness'),
            ('skirt_depth','Skirt depth'),('re_hole','RE opening diameter'),('ce_hole','CE opening diameter'),('port_offset','RE/CE centre offset')]))
        row.addWidget(self.settings_group('Carrier & WE guide (mm)',[
            ('rod_diameter','Rod diameter'),('rod_length','Rod length'),('shoulder_diameter','Carrier shoulder diameter'),
            ('tip_below_shoulder','Tip below shoulder'),('immersion','Target tip immersion'),('we_clearance','WE diametral clearance'),('funnel_diameter','Guide mouth diameter')]))
        l.addLayout(row); self.sketch=CapSketch(self.s); l.addWidget(self.sketch)
        actions=QHBoxLayout(); actions.addWidget(button('Update sketch',self.update_sketch)); actions.addWidget(button('Export STL + OpenSCAD…',self.export_cap,True)); actions.addStretch(); l.addLayout(actions)
        self.geometry_note=self.note('The shoulder sets tip position, not liquid level. Default target: liquid surface 35 mm below shoulder. RE/CE need separate collars/clamps. Dry contact hardware is not included in this print.'); l.addWidget(self.geometry_note)
        self.configuration_actions(l)
    def make_robot(self):
        w,l=self.page(True); l.addWidget(self.note('Coordinates below are simulation placeholders in mm, not calibrated Dobot targets. Hardware movement and gripper control require lab verification.'))
        l.addWidget(self.settings_group('Rack', [('rack_columns','Rack columns',1,20),('rack_pitch','Slot pitch (mm)'),('rack_x','First slot X (mm)',-400,400),('rack_y','First slot Y (mm)',-400,400),('rack_z','Gripping Z (mm)',-100,300),('safe_z','Travel Z (mm)',-100,300)]))
        row=QHBoxLayout()
        for prefix,title in (('cell','Cell'),('rinse','Rinse beaker')):
            row.addWidget(self.settings_group(title,[(prefix+'_x','X (mm)',-400,400),(prefix+'_y','Y (mm)',-400,400),(prefix+'_z','Gripping / dipping Z (mm)',-100,300)]))
        l.addLayout(row); l.addWidget(self.settings_group('Connection',[('robot_port','Dobot serial port')]))
        l.addWidget(self.note('Gripper commissioning: verify installed dobotkit version and supported end-effector calls, then test open/close without an electrode. Reported XYZ alone cannot confirm pickup.'))
        self.configuration_actions(l); l.addStretch()
    def make_camera(self):
        w,l=self.page(); l.addWidget(self.note('Live camera capture is independent of the simulated experiment. Windows uses DirectShow; macOS uses the default OpenCV backend.'))
        g=QGroupBox('Camera connection'); form=QFormLayout(g); self.field(form,'camera_index','Device index (-1 = search 0–4)',-1,20); l.addWidget(g)
        actions=QHBoxLayout(); self.connect_camera=button('Connect camera',self.camera_connect,True); self.disconnect_camera=button('Disconnect',self.camera_disconnect); self.disconnect_camera.setEnabled(False)
        self.snapshot=button('Save snapshot…',self.camera_snapshot); self.snapshot.setEnabled(False)
        actions.addWidget(self.connect_camera); actions.addWidget(self.disconnect_camera); actions.addWidget(self.snapshot); actions.addStretch(); l.addLayout(actions)
        self.camera_status=QLabel('Camera disconnected'); l.addWidget(self.camera_status)
        self.preview=QLabel('Camera preview\nConnect a camera to begin'); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setMinimumSize(480,320); self.preview.setObjectName('preview'); l.addWidget(self.preview,1)
    def read_settings(self):
        values={}
        for key,f in self.fields.items():
            if isinstance(f,QComboBox): values[key]=f.currentData()
            elif isinstance(f,(QSpinBox,QDoubleSpinBox)): values[key]=f.value()
            else: values[key]=f.text()
        return Settings(**values).validate()
    def update_sketch(self):
        try:
            self.sketch.s=self.read_settings(); self.sketch.update()
            s=self.sketch.s
            self.geometry_note.setText(f'Target liquid surface: {s.tip_below_shoulder-s.immersion:.1f} mm below shoulder. RE/CE need separate collars/clamps. Dry contact hardware is not included in this print.')
        except Exception as exc: QMessageBox.warning(self,'Check geometry',str(exc))
    def export_cap(self):
        try: s=self.read_settings()
        except Exception as exc: QMessageBox.warning(self,'Check geometry',str(exc)); return
        folder=QFileDialog.getExistingDirectory(self,'Choose cap export folder',str(ROOT/'cad'))
        if folder:
            try:
                from .cad import export_cap
                path=export_cap(s,folder); Path(folder,'cap_settings.json').write_text(json.dumps(asdict(s),indent=2))
                QMessageBox.information(self,'Cap exported',f'Closed-solid STL and editable OpenSCAD saved to:\n{path.parent}\n\nMeasure the rim and verify fit before lab use.')
            except Exception as exc: QMessageBox.warning(self,'Export failed',str(exc))
    def start_run(self):
        if self.worker and self.worker.isRunning(): return
        try: s=self.read_settings()
        except Exception as exc: QMessageBox.warning(self,'Check configuration',str(exc)); return
        self.s=s; self.plot.data={}; self.plot_selection.clear(); self.plot_selection.addItem('All electrodes',None)
        for index in range(1,s.electrodes+1): self.plot_selection.addItem(f'Electrode {index}',index)
        self.plot.update(); self.log.clear(); self.progress.setRange(0,s.electrodes); self.progress.setValue(0)
        self.start.setEnabled(False); self.pause.setEnabled(True); self.stop.setEnabled(True); self.paused=False; self.pause.setText('Pause')
        for index in (1,2,3): self.pages.widget(index).setEnabled(False)
        self.worker=RunWorker(s); self.worker.event.connect(self.on_event); self.worker.point.connect(self.plot.add); self.worker.result.connect(self.on_result)
        self.worker.finished.connect(self.on_finished); self.worker.start()
    def select_plot(self):
        self.plot.selected=self.plot_selection.currentData(); self.plot.update()
    def on_event(self,event):
        self.state.setText(f"Electrode {event['electrode']} · {event['state'].capitalize()}")
        self.log.appendPlainText(f"{event['time'][11:19]}  {event['detail']}")
        if event['state']=='done': self.progress.setValue(event['electrode'])
    def on_result(self,folder,status):
        self.output=Path(folder) if folder else None; self.state.setText(status.capitalize()); self.statusBar().showMessage(f'Run {status} · {folder}')
    def on_finished(self):
        self.start.setEnabled(True); self.pause.setEnabled(False); self.stop.setEnabled(False)
        for index in (1,2,3): self.pages.widget(index).setEnabled(True)
        if self._close_pending: self.close()
    def pause_run(self):
        if not self.worker: return
        self.paused=not self.paused
        self.worker.control.resume.clear() if self.paused else self.worker.control.resume.set()
        self.pause.setText('Resume' if self.paused else 'Pause'); self.state.setText('Paused' if self.paused else 'Resuming…')
    def stop_run(self):
        if self.worker:
            self.worker.control.cancel.set(); self.worker.control.resume.set(); self.pause.setEnabled(False); self.stop.setEnabled(False); self.state.setText('Stopping…')
    def open_output(self):
        path=self.output or ROOT/'runs'; path.mkdir(exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def camera_connect(self):
        if self.camera and self.camera.isRunning(): return
        self.last_frame=None; self.snapshot.setEnabled(False); self.camera_status.setText('Searching for camera…')
        self.camera=CameraWorker(self.fields['camera_index'].value()); self.camera.frame.connect(self.on_frame); self.camera.status.connect(self.camera_status.setText)
        self.camera.finished.connect(self.camera_finished); self.camera.start(); self.connect_camera.setEnabled(False); self.disconnect_camera.setEnabled(True)
    def camera_disconnect(self):
        if self.camera: self.camera.requestInterruption()
        self.disconnect_camera.setEnabled(False); self.camera_status.setText('Disconnecting…')
    def camera_finished(self):
        self.connect_camera.setEnabled(True); self.disconnect_camera.setEnabled(False)
        if self.camera_status.text()=='Disconnecting…': self.camera_status.setText('Camera disconnected')
        if self._close_pending: self.close()
    def on_frame(self,image):
        self.last_frame=image; self.snapshot.setEnabled(True)
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def camera_snapshot(self):
        if self.last_frame is None: return
        name,_=QFileDialog.getSaveFileName(self,'Save camera snapshot',str(ROOT/'runs'/'camera.png'),'PNG (*.png)')
        if name and not self.last_frame.save(name): QMessageBox.warning(self,'Snapshot failed','Could not write image')
    def closeEvent(self,event):
        running=self.worker and self.worker.isRunning(); camera_running=self.camera and self.camera.isRunning()
        if running or camera_running:
            self._close_pending=True
            if running: self.stop_run()
            if camera_running: self.camera_disconnect()
            self.statusBar().showMessage('Stopping background workers before closing…'); event.ignore()
        else: event.accept()

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
QPushButton:disabled { background:#eef2f5; color:#a4b1ba; border-color:#e0e6eb; }
QSpinBox,QDoubleSpinBox,QLineEdit,QComboBox { border:1px solid #cad7df; border-radius:5px; padding:7px; background:white; selection-background-color:#0d8a7d; }
QSpinBox:focus,QDoubleSpinBox:focus,QLineEdit:focus,QComboBox:focus { border:1px solid #0d8a7d; }
QProgressBar { border:none; background:#e9eff3; border-radius:5px; height:20px; text-align:center; }
QProgressBar::chunk { background:#0d9b8d; border-radius:5px; }
QPlainTextEdit { border:none; color:#647988; font-family:"Menlo","Consolas"; font-size:11px; }
QScrollArea { border:none; }
#preview { background:#152f3c; color:#a8bec9; border-radius:10px; }
QStatusBar { color:#647988; background:#edf3f6; }
'''

def main():
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=Window(); window.show(); sys.exit(app.exec())

if __name__=='__main__': main()
