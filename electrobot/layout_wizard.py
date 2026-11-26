"""Guided, non-moving layout search with explicit teaching and preview/apply."""
from dataclasses import asdict,replace
from PySide6.QtCore import Qt,QPointF,Signal
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QPushButton,QDoubleSpinBox,QSpinBox,QCheckBox,QTabWidget,QScrollArea)
from .config import Settings


class PlanPreview(QWidget):
    def __init__(self):
        super().__init__(); self.settings=None; self.setMinimumSize(420,310)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#f4f8fa')); p.setPen(QColor('#234452'))
        p.drawText(16,24,'TOP VIEW · checked transfer segments and proposed stations')
        s=self.settings
        if not s:
            p.drawText(16,65,'Find a layout to preview its connected transfer routes.'); return
        nodes=s.transfer_plan['nodes']; xs=[0]+[n[0] for n in nodes]; ys=[0]+[n[1] for n in nodes]
        scale=min((self.width()-100)/max(1,max(xs)-min(xs)),(self.height()-100)/max(1,max(ys)-min(ys)))
        def xy(x,y): return QPointF(self.width()/2+(x-(min(xs)+max(xs))/2)*scale,self.height()/2+10-(y-(min(ys)+max(ys))/2)*scale)
        p.setPen(QPen(QColor('#c9d8df'),1))
        for a,b in s.transfer_plan['edges']: p.drawLine(xy(*nodes[a][:2]),xy(*nodes[b][:2]))
        # Preview the complete handling sequence, including initial entry and
        # consecutive rack slots, using exactly the execution/preflight contract.
        rack=[s.rack_pose(i) for i in range(1,s.electrodes+1)]
        cell=(s.cell_x,s.cell_y,s.cell_z); rinse=(s.rinse_x,s.rinse_y,s.rinse_z)
        p.setPen(QPen(QColor('#24a496'),1.4))
        route=s.planned_route(s.transfer_plan['initial_pose'])
        for (_,a),(_,b) in zip(route,route[1:]): p.drawLine(xy(*a[:2]),xy(*b[:2]))
        start=xy(*s.transfer_plan['initial_pose'][:2]); p.setPen(QPen(QColor('#d97706'),2))
        p.drawEllipse(start,5,5); p.drawText(start+QPointF(-45,5),'Start')
        for i,r in enumerate(rack,1):
            q=xy(*r[:2]); p.setPen(QColor('#635bce')); p.setBrush(QColor('#635bce')); p.drawEllipse(q,3.5,3.5)
            p.drawText(q+QPointF(5,-4),str(i))
        for point,label,color,diameter in ((cell,'Cell','#08796f',s.beaker_diameter),(rinse,'Rinse','#3285c8',s.rinse_beaker_diameter)):
            q=xy(*point[:2]); p.setPen(QPen(QColor(color),2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(q,diameter*scale/2,diameter*scale/2); p.drawText(q+QPointF(7,-7),label)
        p.setPen(QColor('#234452')); p.drawText(16,self.height()-14,'Green: selected transfer routes · grey: sampled network · no obstacle model')


class LayoutWizard(QDialog):
    search_requested=Signal(dict); capture_requested=Signal(str); cancel_requested=Signal(); apply_requested=Signal(dict)
    def __init__(self,parent,settings):
        super().__init__(parent); self.base=settings; self.proposal=None; self.busy=False; self.available=False
        self.connected=False; self.searching=False
        self.setWindowTitle('Find a working layout'); self.resize(1040,820); self.setMinimumSize(850,680)
        layout=QVBoxLayout(self)
        intro=QLabel('Teach the fixture heights, choose capacity, then query the controller. Planning never moves the robot or lowers your clearance height.'); intro.setWordWrap(True); layout.addWidget(intro)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1)
        page=QWidget(); form=QFormLayout(page); self.fields={}
        note=QLabel('Use Manual robot to jog to each position, then return here and click Use current position. Cell and rinse capture XYZ; rack captures pickup Z. You may also enter previously taught coordinates.'); note.setWordWrap(True); form.addRow(note)
        self.manual=QPushButton('Go to Manual robot'); self.manual.clicked.connect(self.go_manual); form.addRow(self.manual)
        specs=[('rack_z','Rack pickup Z'),('cell_x','Cell X'),('cell_y','Cell Y'),('cell_z','Cell seating Z'),
               ('rinse_x','Rinse X'),('rinse_y','Rinse Y'),('rinse_z','Rinse dipping Z'),('safe_z','Clearance / Travel Z'),('tool_r','Common tool R (°)')]
        for key,label in specs:
            spin=QDoubleSpinBox(); spin.setRange(-90 if key=='tool_r' else -400,90 if key=='tool_r' else 400)
            spin.setDecimals(2); spin.setValue(getattr(settings,key)); spin.valueChanged.connect(self.invalidate)
            form.addRow(label,spin); self.fields[key]=spin
        self.capture_buttons=[]
        for role,label in (('rack','Rack pickup Z'),('cell','Cell XYZ'),('rinse','Rinse XYZ'),('clearance','Clearance Z')):
            b=QPushButton('Use current position → '+label); b.clicked.connect(lambda checked=False,r=role:self.capture_requested.emit(r)); form.addRow(b); self.capture_buttons.append(b)
        self.confirm=QCheckBox('I have checked these heights and clearance with the actual fixtures and electrode.')
        self.confirm.toggled.connect(self.update_buttons); form.addRow(self.confirm)
        for spin in self.fields.values(): spin.valueChanged.connect(lambda:self.confirm.setChecked(False))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page); self.tabs.addTab(scroll,'1 · Teach positions')
        search=QWidget(); sl=QVBoxLayout(search); sf=QFormLayout(); sl.addLayout(sf)
        self.count=QSpinBox(); self.count.setRange(1,100); self.count.setValue(settings.electrodes if settings.electrodes>3 else 32)
        self.spacing=QDoubleSpinBox(); self.spacing.setRange(10,100); self.spacing.setValue(max(36,min(100,settings.rack_pitch)))
        sf.addRow('Electrodes requested',self.count); sf.addRow('Minimum slot spacing (mm)',self.spacing)
        self.count.valueChanged.connect(self.invalidate); self.spacing.valueChanged.connect(self.invalidate)
        text=QLabel('Searches regular radial racks in the front workspace: radii 120–340 mm, angles −90° to +90°, up to four rows. Respects enabled application bounds and holder spacing; keeps the taught cell/rinse positions. A smaller result is the best found in this sampled search, not the robot’s absolute capacity. Unsupported controller queries abort the search.'); text.setWordWrap(True); sl.addWidget(text)
        text=QLabel('No motion during search. Every connecting segment and vertical stroke is sampled at the configured route spacing. The preview includes approximate beaker footprints, but no obstacle, cable or swept-gripper collision model.'); text.setWordWrap(True); sl.addWidget(text); sl.addStretch()
        self.tabs.addTab(search,'2 · Find layout')
        preview=QWidget(); pl=QVBoxLayout(preview); self.summary=QLabel('No proposed layout yet.'); self.summary.setWordWrap(True); pl.addWidget(self.summary)
        self.preview=PlanPreview(); pl.addWidget(self.preview,1)
        self.review=QCheckBox('I reviewed the proposed fixture layout and transfer routes.'); self.review.toggled.connect(self.update_buttons); pl.addWidget(self.review)
        self.tabs.addTab(preview,'3 · Review and apply')
        self.status=QLabel('Connect and home in Hardware to query limits. Controller search is unavailable in Simulation.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        buttons=QHBoxLayout(); self.find=QPushButton('Find layout · no movement'); self.cancel=QPushButton('Cancel search'); self.apply=QPushButton('Apply layout and routes'); close=QPushButton('Close')
        for b in (self.find,self.cancel,self.apply,close): buttons.addWidget(b)
        layout.addLayout(buttons); self.find.clicked.connect(self.start); self.cancel.clicked.connect(self.cancel_requested.emit)
        self.apply.clicked.connect(self.apply_result); close.clicked.connect(self.close); self.update_buttons()
    def go_manual(self):
        self.parent().nav.setCurrentRow(1); self.hide()
    def settings(self):
        return replace(self.base,transfer_plan={},**{k:w.value() for k,w in self.fields.items()})
    def invalidate(self,*args):
        self.proposal=None; self.preview.settings=None; self.preview.update(); self.review.setChecked(False)
        self.summary.setText('Inputs changed; find a new layout.'); self.update_buttons()
    def set_available(self,available,connected,busy=False):
        self.available=available; self.connected=connected; self.busy=busy; self.update_buttons()
    def update_buttons(self):
        self.find.setEnabled(self.available and not self.busy and self.confirm.isChecked())
        self.cancel.setEnabled(self.busy and self.searching)
        self.apply.setEnabled(not self.busy and self.proposal is not None and self.review.isChecked())
        for b in self.capture_buttons: b.setEnabled(self.connected and not self.busy)
        for w in [*self.fields.values(),self.count,self.spacing,self.confirm,self.manual]: w.setEnabled(not self.busy)
    def start(self):
        self.invalidate(); self.busy=True; self.searching=True; self.update_buttons(); self.status.setText('Checking the taught positions; no motion…')
        self.search_requested.emit({'settings':asdict(self.settings()),'count':self.count.value(),'spacing':self.spacing.value()})
    def event_received(self,event):
        if event['kind']=='pose':
            pose=event['pose']; role=event['role']
            values={'rack':{'rack_z':pose['z']},'clearance':{'safe_z':pose['z']},
                    'cell':{f'cell_{a}':pose[a] for a in 'xyz'},'rinse':{f'rinse_{a}':pose[a] for a in 'xyz'}}[role]
            for key,value in values.items(): self.fields[key].setValue(value)
            self.confirm.setChecked(False); self.status.setText(f'Captured {role} from fresh robot feedback. Common R remains {self.fields["tool_r"].value():g}°; confirm the fixture heights.')
        elif event['kind']=='progress': self.status.setText(event['text'])
        elif event['kind']=='result':
            self.proposal=Settings(**event['settings']); self.preview.settings=self.proposal; self.preview.update()
            s=self.proposal; p=s.transfer_plan
            self.summary.setText(f'{s.electrodes}/{p["requested"]} requested electrodes · {s.rack_columns} slots/row · radius {s.rack_radius:g} mm · row pitch {s.rack_pitch:g} mm · angle step {s.rack_angle_step:g}°.\n'
                f'Best capacity in this sampled search: {p["capacity"]}. Heights preserved: rack {s.rack_z:g}, cell {s.cell_z:g}, rinse {s.rinse_z:g}, clearance {s.safe_z:g} mm. {p["queries"]} controller queries.\n'
                'Applying clears calibration/fixture readiness. Check physical clearance before rehearsal; controller acceptance is not collision clearance.')
            self.tabs.setCurrentIndex(2)
    def apply_result(self):
        if self.proposal is not None and not self.busy and self.review.isChecked(): self.apply_requested.emit(asdict(self.proposal))
    def closeEvent(self,event):
        if self.searching: self.cancel_requested.emit()
        event.accept()
