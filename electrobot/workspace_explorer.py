"""Native workspace explorer; no click or scan commands robot movement."""
import csv
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from PySide6.QtCore import Qt,QPointF,QRectF,Signal
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QDoubleSpinBox,
    QAbstractItemView,QPushButton,QComboBox,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox)
from .workspace_map import scan_axes,validate_saved_map


class WorkspacePlot(QWidget):
    selected=Signal(float,float)
    def __init__(self,explorer):
        super().__init__(); self.explorer=explorer; self.setMinimumSize(420,330); self.points={}; self.axes=None; self.choice=None
    def transform(self):
        xs,ys,_=self.axes
        scale=min((self.width()-80)/max(50,xs[-1]-xs[0]),(self.height()-85)/max(50,ys[-1]-ys[0]))
        cx,cy=(xs[0]+xs[-1])/2,(ys[0]+ys[-1])/2
        return lambda x,y:QPointF(self.width()/2+(x-cx)*scale,self.height()/2-(y-cy)*scale),scale
    def state(self,x,y):
        zs=self.axes[2]; z=self.explorer.view.currentData()
        values=[self.points.get((x,y,h)) for h in (zs if z is None else [z])]
        if any(v is False for v in values): return False
        return True if all(v is True for v in values) else None
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.fillRect(self.rect(),QColor('#f4f8fa'))
        p.setPen(QColor('#234452')); p.drawText(14,22,'Controller reachability · XY samples (mm), +Y up')
        if not self.axes:
            p.drawText(20,75,'Scan a Z height or load a saved map. No robot movement.'); p.end(); return
        xy,scale=self.transform(); xs,ys,zs=self.axes
        radius=max(3,min(9,scale*min(self.explorer.data['spec']['x_step'],self.explorer.data['spec']['y_step'])*.25))
        for x in xs:
            for y in ys:
                state=self.state(x,y); color='#0b9b82' if state is True else '#d07b71' if state is False else '#c9d3da'
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color)); p.drawEllipse(xy(x,y),radius,radius)
        # Station markers are XY projections, not a claim that their Z was queried.
        s=self.explorer.settings
        p.setPen(QPen(QColor('#635bce'),1)); p.setBrush(Qt.BrushStyle.NoBrush)
        stations=[(*s.rack_pose(i)[:2],str(i)) for i in range(s.first_electrode,s.first_electrode+s.electrodes)]
        stations += [(s.cell_x,s.cell_y,'C'),(s.rinse_x,s.rinse_y,'R')]
        for x,y,label in stations:
            if xs[0]<=x<=xs[-1] and ys[0]<=y<=ys[-1]:
                q=xy(x,y); p.drawRect(QRectF(q.x()-5,q.y()-5,10,10)); p.drawText(q+QPointF(7,-5),label)
        if self.choice:
            p.setPen(QPen(QColor('#d97706'),2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(xy(*self.choice),12,12)
        p.setPen(QColor('#234452'))
        p.drawText(12,self.height()-38,f'X {xs[0]:g}…{xs[-1]:g}  |  Y {ys[0]:g}…{ys[-1]:g}')
        p.drawText(12,self.height()-17,'Green: accepted samples  Red: rejected  Grey: not queried; no interpolation')
        p.end()
    def mousePressEvent(self,event):
        if not self.axes: return
        xy,scale=self.transform(); xs,ys,_=self.axes
        cx,cy=(xs[0]+xs[-1])/2,(ys[0]+ys[-1])/2
        x=cx+(event.position().x()-self.width()/2)/scale; y=cy-(event.position().y()-self.height()/2)/scale
        x=min(xs,key=lambda v:abs(v-x)); y=min(ys,key=lambda v:abs(v-y))
        self.choice=(x,y); self.selected.emit(x,y); self.update()


class WorkspaceExplorer(QDialog):
    scan_requested=Signal(dict); cancel_requested=Signal(); target_selected=Signal(tuple)
    def __init__(self,parent,settings):
        super().__init__(parent); self.settings=settings; self.data={}; self.scanning=False; self.allowed=False
        self.setWindowTitle('Workspace explorer — query limits without moving'); self.resize(1100,820)
        layout=QVBoxLayout(self)
        note=QLabel('Map controller-accepted XYZ/R poses without moving. Start with one Z and a coarse XY grid; use a Z range to test a vertical span.\nGreen means the controller accepted those samples, not obstacle clearance or a measured physical workspace. Z is robot tool Z, not bench height.'); note.setWordWrap(True); layout.addWidget(note)
        grid=QGridLayout(); self.inputs={}
        defaults={'x':(-300,300,50),'y':(-300,300,50),'z':(settings.safe_z,settings.safe_z,25)}
        for row,axis in enumerate('xyz'):
            grid.addWidget(QLabel(axis.upper()+' (mm)'),row,0)
            for col,(suffix,label,value) in enumerate(zip(('min','max','step'),('From','To','Step'),defaults[axis])):
                grid.addWidget(QLabel(label),row,col*2+1); spin=QDoubleSpinBox(); spin.setDecimals(2)
                spin.setRange(.5 if suffix=='step' else -400,400); spin.setValue(value)
                self.inputs[axis+'_'+suffix]=spin; grid.addWidget(spin,row,col*2+2)
        self.r=QDoubleSpinBox(); self.r.setRange(-90,90); self.r.setValue(settings.tool_r)
        grid.addWidget(QLabel('Fixed R (°)'),0,7); grid.addWidget(self.r,0,8)
        self.count=QLabel(); grid.addWidget(self.count,1,7,2,2); layout.addLayout(grid)
        for spin in [*self.inputs.values(),self.r]: spin.valueChanged.connect(self.estimate)
        actions=QHBoxLayout(); self.scan=QPushButton('Scan controller · no movement'); self.cancel=QPushButton('Stop scan')
        self.load=QPushButton('Load map…'); self.save=QPushButton('Save JSON…'); self.csv=QPushButton('Export CSV…')
        for b in (self.scan,self.cancel,self.load,self.save,self.csv): actions.addWidget(b)
        self.scan.clicked.connect(self.start_scan); self.cancel.clicked.connect(self.cancel_requested.emit)
        self.load.clicked.connect(self.load_map); self.save.clicked.connect(lambda:self.export_map(False)); self.csv.clicked.connect(lambda:self.export_map(True))
        layout.addLayout(actions); self.progress=QProgressBar(); layout.addWidget(self.progress)
        self.status=QLabel('Connect and home in Hardware to scan. Saved maps can be inspected offline.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        viewrow=QHBoxLayout(); viewrow.addWidget(QLabel('View')); self.view=QComboBox(); viewrow.addWidget(self.view,1); layout.addLayout(viewrow)
        body=QHBoxLayout(); self.plot=WorkspacePlot(self); body.addWidget(self.plot,3)
        side=QVBoxLayout(); self.selection=QLabel('Click a sample to inspect XYZ values.'); self.selection.setWordWrap(True); side.addWidget(self.selection)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Z (mm)','Controller','Scan bounds'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.currentCellChanged.connect(lambda *args:self.update_buttons())
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setMaximumWidth(340)
        side.addWidget(self.table,1); self.copy_target=QPushButton('Copy selected pose to Manual target · no move'); side.addWidget(self.copy_target)
        self.copy_target.clicked.connect(self.copy_pose); body.addLayout(side,2); layout.addLayout(body,1)
        legend=QLabel('C/R and numbered squares are current station XY projections; they do not certify their heights. Maps apply to the scanned R and controller/tool configuration.\nUse Check planned route before handling; sampled vertical acceptance does not certify every intermediate pose. Loading/copying a map never moves or teaches the arm.'); legend.setWordWrap(True); layout.addWidget(legend)
        self.plot.selected.connect(self.select_column); self.view.currentIndexChanged.connect(self.refresh_view)
        self.estimate(); self.update_buttons()
    def spec(self): return {**{k:f.value() for k,f in self.inputs.items()},'r':self.r.value()}
    def estimate(self):
        try:
            axes=scan_axes(self.spec())
            self.count.setText(f'{math.prod(len(a) for a in axes)} queries\nCoarse first; max 5000')
        except ValueError as exc: self.count.setText(str(exc))
    def set_available(self,allowed): self.allowed=allowed; self.update_buttons()
    def update_buttons(self):
        self.scan.setEnabled(self.allowed and not self.scanning); self.cancel.setEnabled(self.scanning)
        self.load.setEnabled(not self.scanning)
        for widget in [*self.inputs.values(),self.r]: widget.setEnabled(not self.scanning)
        for b in (self.save,self.csv): b.setEnabled(bool(self.data.get('points')) and not self.scanning)
        self.copy_target.setEnabled(bool(self.selected_pose()) and not self.scanning)
    def start_scan(self):
        try: scan_axes(self.spec())
        except ValueError as exc: QMessageBox.warning(self,'Scan parameters',str(exc)); return
        self.scanning=True; self.update_buttons(); self.status.setText('Querying controller; no movement commands are sent.')
        self.scan_requested.emit(self.spec())
    def handle_event(self,event):
        kind=event['kind']
        if kind=='start':
            self.data={**event['metadata'],'points':[]}; self.plot.points={}; self.plot.choice=None
            self.plot.axes=scan_axes(self.data['spec']); self.view.blockSignals(True); self.view.clear()
            self.view.addItem('All sampled Z heights · vertical-span intersection',None)
            for z in self.plot.axes[2]: self.view.addItem(f'Z = {z:g} mm',z)
            self.view.setCurrentIndex(1 if len(self.plot.axes[2])==1 else 0); self.view.blockSignals(False)
            self.progress.setRange(0,event['total']); self.progress.setValue(0); self.table.setRowCount(0)
        elif kind=='point':
            p=event['point']; self.data['points'].append(p); self.plot.points[tuple(p[:3])]=p[4]
            self.progress.setValue(event['done']); self.status.setText(f'Queried {event["done"]}/{event["total"]} poses · no movement')
        elif kind=='finish':
            self.data['complete']=event['complete']; self.data['finished_utc']=datetime.now(timezone.utc).isoformat()
            self.scanning=False; self.status.setText(('Complete' if event['complete'] else 'Partial map — cancelled or query failed; grey points remain unknown')+' · no physical movement tested')
        self.plot.update(); self.refresh_selection(); self.update_buttons()
    def refresh_view(self): self.plot.update(); self.refresh_selection()
    def selected_pose(self):
        if not self.plot.choice or not self.plot.axes: return None
        x,y=self.plot.choice; z=self.view.currentData()
        if z is None:
            row=self.table.currentRow()
            if row<0: return None
            z=self.plot.axes[2][row]
        return (x,y,z,self.data['spec']['r']) if self.plot.points.get((x,y,z)) is True else None
    def select_column(self,x,y): self.refresh_selection()
    def refresh_selection(self):
        if not self.plot.choice or not self.plot.axes: self.copy_target.setEnabled(False); return
        x,y=self.plot.choice; zs=self.plot.axes[2]; previous=self.table.currentRow()
        self.table.blockSignals(True); self.table.setRowCount(len(zs)); points={tuple(p[:3]):p for p in self.data['points']}
        for row,z in enumerate(zs):
            p=points.get((x,y,z)); texts=(f'{z:g}','Accepted' if p and p[4] else 'Rejected' if p else 'Unknown',
                                         'Inside' if p and p[5] else 'Outside' if p else '—')
            for col,t in enumerate(texts): self.table.setItem(row,col,QTableWidgetItem(t))
        accepted=sum(self.plot.points.get((x,y,z)) is True for z in zs)
        self.selection.setText(f'X {x:g}, Y {y:g} mm; R {self.data["spec"]["r"]:g}°\n{accepted}/{len(zs)} Z samples accepted.\nSampled span {zs[-1]-zs[0]:g} mm; intervals are not interpolated.')
        if previous>=0: self.table.setCurrentCell(min(previous,len(zs)-1),0)
        self.table.blockSignals(False)
        self.copy_target.setEnabled(bool(self.selected_pose()) and not self.scanning)
    def copy_pose(self):
        pose=self.selected_pose()
        if pose: self.target_selected.emit(pose); self.status.setText('Copied to Manual robot target fields. No movement commanded; recheck the route on current hardware.')
    def export_map(self,as_csv):
        name,_=QFileDialog.getSaveFileName(self,'Export workspace map','workspace-map.csv' if as_csv else 'workspace-map.json','CSV (*.csv)' if as_csv else 'JSON (*.json)')
        if not name: return
        try:
            if as_csv:
                with Path(name).open('w',newline='') as stream:
                    writer=csv.writer(stream); writer.writerow(['x_mm','y_mm','z_mm','r_deg','controller_accepted','inside_configured_bounds']); writer.writerows(self.data['points'])
            else: Path(name).write_text(json.dumps(self.data,indent=2)+'\n')
        except Exception as exc: QMessageBox.warning(self,'Export failed',str(exc))
    def load_map(self):
        name,_=QFileDialog.getOpenFileName(self,'Load controller workspace map','','JSON (*.json)')
        if not name: return
        try:
            data=validate_saved_map(json.loads(Path(name).read_text())); points=data.pop('points')
            self.handle_event({'kind':'start','metadata':data,'total':math.prod(len(a) for a in scan_axes(data['spec']))})
            self.data['points']=points; self.plot.points={tuple(p[:3]):p[4] for p in points}
            self.scanning=False; self.progress.setValue(len(points)); self.plot.update(); self.update_buttons()
            self.status.setText(f'Saved map from {data.get("started_utc","unknown time")} at R={data["spec"]["r"]:g}°. Historical query data; recheck on current hardware.')
        except Exception as exc: QMessageBox.warning(self,'Cannot load map',str(exc))
    def closeEvent(self,event):
        if self.scanning: self.cancel_requested.emit()
        event.accept()
