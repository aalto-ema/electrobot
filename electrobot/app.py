import json
import sys
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl
from PySide6.QtGui import QPixmap,QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QLabel,QPushButton,
    QVBoxLayout,QHBoxLayout,QGridLayout,QListWidget,QStackedWidget,QGroupBox,QFormLayout,
    QDoubleSpinBox,QSpinBox,QLineEdit,QComboBox,QCheckBox,QScrollArea,QProgressBar,
    QPlainTextEdit,QFileDialog,QMessageBox,QSplitter,QTabWidget,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QSizePolicy)
from .config import Settings
from .calibration_widgets import CalibrationDiagram,RobotTracker
from .rack_widgets import RackDiagram
from .worker import DeviceWorker
from .camera import CameraWorker
from .widgets import Plot,CapSketch,CameraPreview,STYLE,button,card

ROOT=Path(__file__).resolve().parent.parent

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Electrobot · Electrochemistry Workbench')
        self.resize(1440,960); self.setMinimumSize(1120,760)
        self.workspace_explorer=None; self.active_command=None
        self.s=Settings(); self.fields={}; self.busy=False; self.running_batch=False
        self.paused=False; self.camera=None; self.last_frame=None; self.output=None
        self._close_pending=False; self._shutdown_sent=False; self.current_pose=None; self.robot_diagnostics={}
        self.device_state={'robot':False,'potentiostat':False,'homed':False,'holding':False}
        if (ROOT/'settings.json').exists():
            try: self.s=Settings(**json.loads((ROOT/'settings.json').read_text())).validate()
            except Exception as exc: self.load_error=str(exc)
        # Device mode is deliberately selected each session; loading a profile never connects hardware.
        self.s.mode='simulation'
        base=QWidget(); self.setCentralWidget(base); shell=QHBoxLayout(base)
        shell.setContentsMargins(0,0,0,0); shell.setSpacing(0)
        sidebar=QWidget(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(195)
        sl=QVBoxLayout(sidebar); sl.setContentsMargins(20,30,20,24)
        brand=QLabel('electrobot'); brand.setObjectName('brand'); sl.addWidget(brand)
        subtitle=QLabel('ELECTROCHEMISTRY\nWORKBENCH'); subtitle.setObjectName('navsub'); sl.addWidget(subtitle); sl.addSpacing(30)
        self.nav=QListWidget(); self.nav.addItems(['Experiment','Manual robot','Settings']); sl.addWidget(self.nav)
        self.sidebar_status=QLabel('Simulation\nNo physical commands'); self.sidebar_status.setObjectName('navsub'); self.sidebar_status.setWordWrap(True); sl.addWidget(self.sidebar_status)
        shell.addWidget(sidebar); content=QWidget(); main=QVBoxLayout(content); main.setContentsMargins(24,22,24,16); main.setSpacing(14)
        header=QHBoxLayout(); self.heading=QLabel('Experiment'); self.heading.setObjectName('heading'); header.addWidget(self.heading); header.addStretch()
        header.addWidget(QLabel('Device mode')); self.mode=QComboBox(); self.mode.addItem('Simulation','simulation'); self.mode.addItem('Hardware','hardware'); self.fields['mode']=self.mode
        header.addWidget(self.mode); self.badge=QLabel('● SIMULATION'); self.badge.setObjectName('badge'); header.addWidget(self.badge); main.addLayout(header)
        self.pages=QStackedWidget(); main.addWidget(self.pages); shell.addWidget(content)
        self.make_dashboard(); self.make_manual(); self.make_settings()
        for key in ('rack_x','rack_y','rack_z','rack_pitch','rack_columns','rack_radius','rack_start_angle','rack_angle_step','cell_x','cell_y','cell_z',
                    'rinse_x','rinse_y','rinse_z','safe_z','tool_r',
                    'workspace_x_min','workspace_x_max','workspace_y_min','workspace_y_max',
                    'workspace_z_min','workspace_z_max','workspace_radius_min','workspace_radius_max'):
            self.fields[key].valueChanged.connect(lambda:self.fields['calibrated'].setChecked(False))
        self.fields['rack_layout'].currentIndexChanged.connect(lambda:self.fields['calibrated'].setChecked(False))
        for key in ('rod_diameter','rod_length','shoulder_diameter','tip_below_shoulder',
                    'cap_thickness','we_clearance','funnel_diameter','rack_socket_clearance','rack_socket_depth','rack_post_height','rack_socket_wall','rack_base_thickness','rack_margin'):
            self.fields[key].valueChanged.connect(lambda:self.fields['fixture_verified'].setChecked(False))
        for key,f in self.fields.items():
            if key.startswith('holder_') or key in ('rack_holder_clearance','rack_seat_depth','rack_deck_thickness','rack_seat_wall','rack_rib_width','rack_hanging_length','rack_tip_clearance','rack_gripper_gap','rack_module_slots','rack_peg_diameter','rack_peg_clearance','rack_peg_length','rack_foot_base','rack_foot_column_diameter','rack_foot_mount_hole'):
                f.valueChanged.connect(lambda:self.fields['fixture_verified'].setChecked(False))
        self.fields['rack_design'].currentIndexChanged.connect(lambda:self.fields['fixture_verified'].setChecked(False))
        for key in ('electrodes','first_electrode'):
            self.fields[key].valueChanged.connect(self.prepare_queue)
        self.prepare_queue()
        for f in self.fields.values():
            signal=f.valueChanged if isinstance(f,(QSpinBox,QDoubleSpinBox)) else f.toggled if isinstance(f,QCheckBox) else f.currentIndexChanged if isinstance(f,QComboBox) else f.textChanged
            signal.connect(self.update_calibration_feedback)
        self.fields['calibrated'].toggled.connect(self.refresh_controls)
        self.fields['fixture_verified'].toggled.connect(self.refresh_controls)
        self.nav.currentRowChanged.connect(self.change_page); self.nav.setCurrentRow(0)
        self.worker=DeviceWorker(ROOT/'runs'); self.worker.state.connect(self.on_devices)
        self.worker.diagnostic.connect(self.on_diagnostic)
        self.worker.workspace_sample.connect(self.on_workspace_sample)
        self.worker.pose.connect(self.on_pose); self.worker.event.connect(self.on_event)
        self.worker.point.connect(self.plot.add); self.worker.result.connect(self.on_result)
        self.worker.completed.connect(self.on_completed); self.worker.finished.connect(self.on_worker_finished); self.worker.start()
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.timer=QTimer(self); self.timer.timeout.connect(lambda:self.plot.update() if self.plot.dirty else None); self.timer.start(100)
        self.validation_issues=[]; self.update_calibration_feedback()
        self.refresh_controls(); self.submit('configure')
        if hasattr(self,'load_error'): self.statusBar().showMessage('Saved settings could not load; using defaults: '+self.load_error)

    def note(self,text):
        l=QLabel(text); l.setWordWrap(True); l.setObjectName('note'); return l
    def page(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(14); self.pages.addWidget(w); return w,l
    def change_page(self,index):
        self.pages.setCurrentIndex(index); self.heading.setText(self.nav.item(index).text())
    def field(self,form,key,label,minimum=None,maximum=None,decimals=None):
        value=getattr(self.s,key)
        if isinstance(value,bool): f=QCheckBox(); f.setChecked(value)
        elif isinstance(value,int):
            f=QSpinBox(); f.setRange(int(minimum if minimum is not None else 1),int(maximum or 100)); f.setValue(value)
        elif isinstance(value,float):
            f=QDoubleSpinBox(); f.setDecimals(decimals if decimals is not None else (4 if key in ('step_v','scan_rate') else 2))
            f.setRange(minimum if minimum is not None else .01,maximum or 10000); f.setValue(value)
            f.setSingleStep(.01 if key.endswith('_v') or key=='scan_rate' else 1)
        else: f=QLineEdit(value)
        f.setMinimumWidth(110); self.fields[key]=f; form.addRow(label,f); return f
    def settings_group(self,title,items):
        g=QGroupBox(title); f=QFormLayout(g); f.setContentsMargins(16,24,16,16); f.setVerticalSpacing(10)
        for item in items: self.field(f,*item)
        return g
    def combo_field(self,form,key,label,options):
        f=QComboBox()
        for text,value in options: f.addItem(text,value)
        f.setCurrentIndex(f.findData(getattr(self.s,key))); self.fields[key]=f; form.addRow(label,f); return f
    def read_settings(self,validate=True):
        values=asdict(self.s)
        for key,f in self.fields.items():
            if isinstance(f,QCheckBox): values[key]=f.isChecked()
            elif isinstance(f,QComboBox): values[key]=f.currentData()
            elif isinstance(f,(QSpinBox,QDoubleSpinBox)): values[key]=f.value()
            else: values[key]=f.text()
        values['end_v']=values['start_v']  # Native PalmSens CV returns to begin potential.
        return Settings(**values).validate() if validate else Settings(**values)
    def apply_settings(self,s):
        connection_keys=[]
        if self.device_state.get('robot'):
            connection_keys.extend(('robot_port','robot_host','robot_ws_port','robot_timeout'))
        if self.device_state.get('potentiostat'): connection_keys.append('potentiostat_id')
        for key in connection_keys:
            field=self.fields[key]
            value=field.value() if isinstance(field,(QSpinBox,QDoubleSpinBox)) else field.text()
            if value!=getattr(s,key):
                raise ValueError('Disconnect devices before loading a different connection profile')
        for key,f in self.fields.items():
            if key=='mode': continue
            f.blockSignals(True)
            try:
                if isinstance(f,QCheckBox): f.setChecked(getattr(s,key))
                elif isinstance(f,QComboBox): f.setCurrentIndex(f.findData(getattr(s,key)))
                elif isinstance(f,(QSpinBox,QDoubleSpinBox)): f.setValue(getattr(s,key))
                else: f.setText(getattr(s,key))
            finally: f.blockSignals(False)
        s.mode=self.mode.currentData(); self.s=s; self.update_sketch(); self.prepare_queue(); self.update_calibration_feedback()
    def update_calibration_feedback(self,*args,invalidate=True):
        if not hasattr(self,'workspace_diagram'): return
        s=self.read_settings(validate=False)
        if self.robot_diagnostics and invalidate:
            self.robot_diagnostics['preflight']='Not checked for current settings'
            self.update_diagnostic_labels()
        self.update_map_feedback(s)
        self.validation_issues=s.calibration_issues()
        try: s.validate()
        except ValueError as exc:
            if not self.validation_issues: self.validation_issues=[((),str(exc))]
        for diagram in (self.calibration_diagram,self.workspace_diagram,self.experiment_tracker,self.manual_tracker,self.rack_diagram): diagram.set_settings(s)
        bad={key for keys,_ in self.validation_issues for key in keys}
        for key,f in self.fields.items():
            f.setStyleSheet('border: 2px solid #c34848;' if key in bad else '')
        messages=list(dict.fromkeys(message for _,message in self.validation_issues))
        if self.robot_diagnostics.get('fault'): messages.append(self.robot_diagnostics['fault'])
        text=('Check settings:\n'+'\n'.join('• '+m for m in messages[:12])+(f'\n… {len(messages)-12} more issues' if len(messages)>12 else '')) if messages else '✓ Dimensions and selected route endpoints are compatible. Physical clearance still needs verification.'
        for label in (self.calibration_feedback,self.workspace_feedback,self.rack_feedback):
            label.setText(text); label.setStyleSheet('color: #b53636;' if messages else 'color: #08796f;')
        if hasattr(self,'worker'): self.refresh_controls()

    def compact_rehearsal_preset(self):
        if self.busy: return
        if self.device_state.get('holding'): return
        self.submit('rehearsal_pose')

    def apply_compact_rehearsal(self,pose):
        if pose is None: return
        from dataclasses import replace
        s=replace(self.read_settings(validate=False),run_name='Compact empty-gripper rehearsal',
            first_electrode=1,electrodes=1,rack_layout='rectangular',rack_x=pose['x'],rack_y=pose['y'],rack_z=pose['z'],
            cell_x=pose['x']+10,cell_y=pose['y'],cell_z=pose['z'],
            rinse_x=pose['x']+10,rinse_y=pose['y']+10,rinse_z=pose['z'],
            safe_z=pose['z']+5,tool_r=pose['r'],robot_velocity=10,robot_acceleration=10,
            settle=1,rinse_dips=1,rinse_dwell=.5,calibrated=False,fixture_verified=False)
        issues=s.calibration_issues()
        try:
            s.validate()
            if issues: raise ValueError('\n'.join(dict.fromkeys(m for _,m in issues)))
        except ValueError as exc:
            self.statusBar().showMessage('Preset not applied: '+str(exc))
            self.calibration_feedback.setText('Preset not applied from the current pose:\n'+str(exc))
            self.calibration_feedback.setStyleSheet('color: #b53636;'); return
        self.apply_settings(s)
        self.statusBar().showMessage('Compact preset applied from fresh pose; no movement commanded. Verify the empty route before marking readiness.')

    def save(self):
        try:
            self.s=self.read_settings(); (ROOT/'settings.json').write_text(json.dumps(asdict(self.s),indent=2))
            self.statusBar().showMessage('Configuration saved'); self.update_sketch()
        except Exception as exc: QMessageBox.warning(self,'Check settings',str(exc))
    def load(self):
        name,_=QFileDialog.getOpenFileName(self,'Load configuration',str(ROOT),'JSON (*.json)')
        if name:
            try: self.apply_settings(Settings(**json.loads(Path(name).read_text())).validate())
            except Exception as exc: QMessageBox.warning(self,'Cannot load configuration',str(exc))

    def make_dashboard(self):
        w,l=self.page()
        devices=QHBoxLayout(); self.robot_status=QLabel('Robot · simulated'); self.pot_status=QLabel('Potentiostat · simulated')
        self.robot_status.setMaximumWidth(240); self.pot_status.setMaximumWidth(270); self.pot_status.setWordWrap(True)
        devices.addWidget(self.robot_status); devices.addWidget(self.pot_status); devices.addStretch()
        self.connect_robot=button('Connect robot',lambda:self.submit('connect_robot')); self.connect_pot=button('Connect potentiostat',lambda:self.submit('connect_potentiostat'))
        self.disconnect=button('Disconnect devices',self.disconnect_devices)
        self.disconnect.setToolTip('Disconnecting the pneumatic gripper turns its pump off; secure any held electrode first.')
        for b in (self.connect_robot,self.connect_pot,self.disconnect): devices.addWidget(b)
        l.addLayout(devices)
        self.mode_note=self.note('Simulation mode · synthetic CV data. Connect a real camera independently if desired.'); l.addWidget(self.mode_note)
        dashboard=QSplitter(Qt.Orientation.Horizontal)
        experiment=QWidget(); experiment_layout=QVBoxLayout(experiment); experiment_layout.setContentsMargins(0,0,0,0); experiment_layout.setSpacing(10)
        dashboard.addWidget(experiment)
        self.setup_box=QWidget(); setup=QHBoxLayout(self.setup_box); setup.setContentsMargins(0,0,0,0); setup.setSpacing(14)
        self.batch_group=self.settings_group('Batch', [('run_name','Run name'),('first_electrode','First rack slot',1,100),('electrodes','Electrodes',1,100),('cycles','CV cycles',1,100)])
        self.cv_group=self.settings_group('Cyclic voltammetry · V vs reference', [('start_v','Start / end (V)',-3,3),('vertex1_v','Upper vertex (V)',-3,3),('vertex2_v','Lower vertex (V)',-3,3),('scan_rate','Scan rate (V/s)',.0001,10)])
        self.rinse_group=self.settings_group('Conditioning & rinse', [('settle','Settle before CV (s)',0,600),('rinse_dips','Rinse dips',1,20),('rinse_dwell','Dwell per dip (s)',0,120)])
        for group in (self.batch_group,self.cv_group,self.rinse_group):
            group.layout().setVerticalSpacing(6)
            group.setStyleSheet('QSpinBox,QDoubleSpinBox,QLineEdit { padding:4px; }')
            setup.addWidget(group,1)
        experiment_layout.addWidget(self.setup_box)
        actions=QHBoxLayout(); self.start=button('▶  Start batch',self.start_run,True); self.pause=button('Pause',self.pause_run); self.stop=button('Stop',self.stop_run); self.stop.setObjectName('danger')
        self.rehearse=button('Robot rehearsal',lambda:self.start_run(rehearsal=True))
        actions.addWidget(self.start); actions.addWidget(self.rehearse); actions.addWidget(self.pause); actions.addWidget(self.stop); actions.addStretch()
        actions.addWidget(button('Run folder',self.open_output)); experiment_layout.addLayout(actions)
        run_status=QHBoxLayout(); self.state=QLabel('Ready'); self.state.setObjectName('metric'); run_status.addWidget(self.state); run_status.addStretch()
        self.progress=QProgressBar(); self.progress.setFixedWidth(180); self.progress.setRange(0,self.s.electrodes); self.progress.setValue(0); run_status.addWidget(self.progress)
        experiment_layout.addLayout(run_status)
        self.main_split=QSplitter(Qt.Orientation.Horizontal)
        graph,gl=card('Electrochemistry'); tools=QHBoxLayout(); tools.addWidget(QLabel('Display')); self.plot_selection=QComboBox(); self.plot_selection.addItem('All electrodes',None)
        self.plot_selection.currentIndexChanged.connect(self.select_plot); tools.addWidget(self.plot_selection); tools.addStretch(); gl.addLayout(tools)
        self.plot=Plot(); self.plot.setMinimumWidth(300); self.plot.setMinimumHeight(210); gl.addWidget(self.plot); self.main_split.addWidget(graph)
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(10)
        camera,cl=card('Camera'); self.preview=CameraPreview(); cl.addWidget(self.preview,1)
        self.camera_status=QLabel('Disconnected'); self.camera_status.setObjectName('note'); self.camera_status.setWordWrap(True); cl.addWidget(self.camera_status)
        buttons=QHBoxLayout(); self.connect_camera=button('Connect',self.camera_connect); self.disconnect_camera=button('Disconnect',self.camera_disconnect); self.snapshot=button('Snapshot',self.camera_snapshot)
        for b in (self.connect_camera,self.disconnect_camera,self.snapshot): buttons.addWidget(b)
        cl.addLayout(buttons); rl.addWidget(camera,3)
        activity,al=card('Activity'); self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(2000); self.log.setMinimumHeight(60); al.addWidget(self.log); rl.addWidget(activity,2)
        self.main_split.addWidget(right)
        electrodes,el=card('Robot & electrode queue')
        self.experiment_diagnostic=self.note('Robot checks: not yet run'); el.addWidget(self.experiment_diagnostic)
        el.addWidget(button('Robot diagnostic details…',self.show_robot_diagnostics))
        self.experiment_tracker=RobotTracker(); self.experiment_tracker.setMinimumHeight(280); el.addWidget(self.experiment_tracker,3)
        el.addWidget(QLabel('Electrode queue'))
        self.queue_table=QTableWidget(0,3); self.queue_table.setHorizontalHeaderLabels(['Rack slot','Electrode','Status']); self.queue_table.verticalHeader().hide()
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setMinimumSize(240,140); el.addWidget(self.queue_table,2)
        dashboard.addWidget(electrodes)
        self.main_split.setSizes([432,380])
        for index,stretch in enumerate((53,47)): self.main_split.setStretchFactor(index,stretch)
        experiment_layout.addWidget(self.main_split,1)
        dashboard.setSizes([812,288]); dashboard.setStretchFactor(0,74); dashboard.setStretchFactor(1,26)
        l.addWidget(dashboard,1)
        self.camera_buttons_update()
    def make_manual(self):
        w,outer=self.page(); split=QSplitter(Qt.Orientation.Horizontal)
        controls=QWidget(); l=QVBoxLayout(controls); l.setContentsMargins(0,0,0,0); l.setSpacing(10)
        split.addWidget(controls); self.manual_tracker=RobotTracker(); split.addWidget(self.manual_tracker)
        split.setSizes([680,420]); outer.addWidget(split,1)
        l.addWidget(self.note('Manual commands use the selected device mode. Home after connection before hardware movement. Stop halts the queue and requires homing again.'))
        actions=QHBoxLayout(); self.manual_buttons=[]; self.motion_buttons=[]
        for text,command in (('Read pose','pose'),('Home robot','home')):
            b=button(text,lambda checked=False,c=command:self.submit(c)); actions.addWidget(b); self.manual_buttons.append(b)
        self.manual_stop=button('Stop robot',self.stop_run); self.manual_stop.setObjectName('danger'); actions.addWidget(self.manual_stop); actions.addWidget(button('Workspace explorer…',self.open_workspace_explorer)); actions.addStretch(); l.addLayout(actions)
        self.pose_label=QLabel('X —    Y —    Z —    R —'); self.pose_label.setObjectName('metric'); l.addWidget(self.pose_label)
        self.manual_diagnostic=self.note('Robot checks: not yet run'); l.addWidget(self.manual_diagnostic)
        checks=QHBoxLayout()
        self.manual_route_check=button('Check planned route · no motion',lambda:self.submit('check_route')); checks.addWidget(self.manual_route_check)
        self.alarm_clear=button('Clear controller alarms',lambda:self.submit('clear_alarms')); checks.addWidget(self.alarm_clear)
        checks.addWidget(button('Diagnostic details…',self.show_robot_diagnostics)); l.addLayout(checks)
        row=QHBoxLayout(); jog,jl=card('Jog'); step_row=QHBoxLayout(); step_row.addWidget(QLabel('Step (mm / degrees)')); self.jog_step=QDoubleSpinBox(); self.jog_step.setRange(.1,20); self.jog_step.setValue(1); step_row.addWidget(self.jog_step); step_row.addStretch(); jl.addLayout(step_row)
        grid=QGridLayout()
        for axis,name in enumerate('XYZR'):
            grid.addWidget(QLabel(name),axis,0)
            for column,sign in ((1,-1),(2,1)):
                b=button(('−' if sign<0 else '+')+name,lambda checked=False,a=axis,v=sign:self.submit('jog',(a,v*self.jog_step.value())))
                grid.addWidget(b,axis,column); self.manual_buttons.append(b); self.motion_buttons.append(b)
        jl.addLayout(grid); row.addWidget(jog,1)
        target,tl=card('Move to target'); form=QFormLayout(); self.target_fields=[]
        for axis,value in zip('XYZR',(200,0,80,0)):
            f=QDoubleSpinBox(); f.setRange(-400,400); f.setValue(value); form.addRow(axis+(' (°)' if axis=='R' else ' (mm)'),f); self.target_fields.append(f)
        tl.addLayout(form); self.target_move=button('Move to XYZ/R',lambda:self.submit('move',tuple(f.value() for f in self.target_fields)),True); tl.addWidget(self.target_move); self.manual_buttons.append(self.target_move); self.motion_buttons.append(self.target_move); row.addWidget(target,1); l.addLayout(row)
        bottom=QHBoxLayout(); grip,gl=card('Gripper'); self.grip_label=self.note('Commanded state: open. No pickup sensor is configured.'); gl.addWidget(self.grip_label)
        for text,closed in (('Release · pump off',False),('Close gripper',True)):
            b=button(text,lambda checked=False,c=closed:self.submit('grip',c)); gl.addWidget(b); self.manual_buttons.append(b)
        b=button('Fully open · pump on',lambda:self.submit('open_fully')); gl.addWidget(b); self.manual_buttons.append(b)
        gl.addWidget(self.note('Normal release turns the pump off and lets the fingers relax. Fully open actively spreads the fingers.')); bottom.addWidget(grip)
        teach,tt=card('Teach station'); self.teach_station=QComboBox(); self.teach_station.addItems(['Rack first slot','Cell seating pose','Rinse dipping pose','Travel height'])
        tt.addWidget(self.teach_station); self.teach_button=button('Use current pose',self.teach_pose); tt.addWidget(self.teach_button)
        tt.addWidget(self.note('Copies reported coordinates into Settings. Save the profile after checking clearance paths.')); bottom.addWidget(teach); l.addLayout(bottom); l.addStretch()
    def settings_tab(self,title):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content=QWidget(); layout=QVBoxLayout(content); layout.setSpacing(16); scroll.setWidget(content); self.settings_tabs.addTab(scroll,title); return layout
    def calibration_tab(self,title,diagram_type=None):
        tab=QWidget(); outer=QVBoxLayout(tab); outer.setContentsMargins(10,10,10,10)
        feedback=self.note(''); outer.addWidget(feedback)
        split=QSplitter(Qt.Orientation.Vertical); outer.addWidget(split,1)
        diagram=diagram_type() if diagram_type else CalibrationDiagram(workspace=True); diagram.setMinimumHeight(240); split.addWidget(diagram)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame); scroll.setMinimumHeight(140)
        content=QWidget(); layout=QVBoxLayout(content); layout.setSpacing(16); scroll.setWidget(content); split.addWidget(scroll)
        split.setChildrenCollapsible(False); split.setSizes([300,400]); split.setStretchFactor(0,0); split.setStretchFactor(1,1)
        split.setHandleWidth(8); split.handle(1).setToolTip('Drag to resize the diagram and settings areas')
        split.setStyleSheet('QSplitter::handle:vertical { background: #d6e0e5; margin: 2px 0; }')
        self.settings_tabs.addTab(tab,title)
        return layout,feedback,diagram,scroll
    def make_settings(self):
        w,l=self.page(); actions=QHBoxLayout(); self.save_button=button('Save configuration',self.save,True); self.load_button=button('Load configuration…',self.load)
        self.placement_export=button('Export placement PDF…',self.export_placement)
        actions.addWidget(self.save_button); actions.addWidget(self.load_button); actions.addWidget(self.placement_export); actions.addStretch(); l.addLayout(actions)
        self.settings_tabs=QTabWidget(); l.addWidget(self.settings_tabs)
        devices=self.settings_tab('Devices'); devices.addWidget(self.note('Hardware packages: requirements-hardware.txt. Start DobotLink on Windows. PalmSens requires its .NET runtime and USB drivers. Connection changes take effect after disconnect/reconnect.'))
        devices.addWidget(self.settings_group('DobotLink connection', [('robot_port','Robot port (auto / COM…)'),('robot_host','DobotLink host'),('robot_ws_port','WebSocket port',1,65535),('robot_timeout','RPC timeout (s)',1,30)]))
        devices.addWidget(self.settings_group('PalmSens & camera', [('potentiostat_id','Potentiostat ID (blank = one device)'),('sdk_timeout','SDK timeout margin (s)',5,120),('camera_index','Camera index (-1 = auto)',-1,20)])); devices.addStretch()
        protocol=self.settings_tab('Measurement defaults'); protocol.addWidget(self.settings_group('Acquisition', [('step_v','Potential step (V)',.0001,1),('reference_label','Reference electrode'),('simulation_speed','Simulation multiplier',.1,100)]))
        acquisition=QGroupBox('Instrument defaults'); f=QFormLayout(acquisition)
        self.combo_field(f,'current_range_ua','Fixed current range',[(f'{v:g} µA',v) for v in (.001,.01,.1,1,10,100,1000,10000)])
        self.combo_field(f,'power_frequency','Mains frequency',[('50 Hz',50),('60 Hz',60)]); protocol.addWidget(acquisition)
        protocol.addWidget(self.note('Native PalmSens CV returns to its start potential. Hardware ignores the simulation multiplier. Current and potential values are recorded from SDK data; CSV time is nominal CV sample time.')); protocol.addStretch()
        robot,self.calibration_feedback,self.calibration_diagram,self.calibration_scroll=self.calibration_tab('Robot calibration')
        self.preset_button=button('Compact rehearsal from current pose',self.compact_rehearsal_preset,True); robot.addWidget(self.preset_button)
        robot.addWidget(self.note('Empty-gripper preset: read the live pose, use it as rack slot 1, offset cell +10 mm X and rinse +10 mm X/+10 mm Y, and set travel Z +5 mm. No movement is commanded. Readiness is cleared.'))
        layout_group=QGroupBox('Rack layout'); lf=QFormLayout(layout_group)
        self.combo_field(lf,'rack_layout','Slot arrangement',[('Rectangular grid','rectangular'),('Radial arcs around robot base','radial')]); robot.addWidget(layout_group)
        robot.addWidget(self.settings_group('Radial layout (mm / degrees)', [('rack_radius','First row radius',1,400),('rack_start_angle','Slot 1 angle (°)',-180,180),('rack_angle_step','Angle between slots (°)',.1,90)]))
        robot.addWidget(self.note('Radial: Columns means slots per arc row; Slot pitch is the radial distance between rows. Angles start on +X and increase towards +Y. First-slot X/Y apply only to rectangular layouts.'))
        row=QHBoxLayout()
        row.addWidget(self.settings_group('Rack (mm)', [('rack_columns','Columns',1,20),('rack_pitch','Slot pitch'),('rack_x','First slot X',-400,400),('rack_y','First slot Y',-400,400),('rack_z','Gripping Z',-100,300),('safe_z','Travel Z',-100,300)]))
        row.addWidget(self.settings_group('Stations (mm)', [('cell_x','Cell X',-400,400),('cell_y','Cell Y',-400,400),('cell_z','Cell seating Z',-100,300),('rinse_x','Rinse X',-400,400),('rinse_y','Rinse Y',-400,400),('rinse_z','Rinse dipping Z',-100,300),('tool_r','Carrier rotation (°)',-90,90)])); robot.addLayout(row)
        robot.addWidget(self.settings_group('Motion', [('robot_velocity','Velocity setting',.1,100),('robot_acceleration','Acceleration setting',.1,100),('motion_timeout','Motion timeout (s)',1,120),('home_timeout','Homing timeout (s)',20,180),('position_tolerance','XYZ tolerance (mm)',.05,5),('rotation_tolerance','R tolerance (°)',.1,5),('grip_dwell','Gripper dwell (s)',.1,10)]))
        robot.addWidget(self.note('XYZ tolerance is the maximum distance between the commanded and reported tool positions; R tolerance is the allowed angular error. Gripper dwell is the wait after an open/close command. Motion/home timeouts limit how long completion is awaited. Velocity and acceleration are SDK settings (0–100), not guaranteed mm/s or mm/s².'))
        for key,tip in {
            'rack_columns':'Slots increase along +X across this many columns, then advance one pitch along +Y.',
            'rack_pitch':'Center-to-center distance between adjacent rack slots in X and Y.',
            'rack_z':'Reported robot tool Z when gripping; not the electrode tip height.',
            'cell_z':'Reported robot tool Z when seating/retrieving the carrier.',
            'rinse_z':'Reported robot tool Z at the bottom of each rinse dip.',
            'safe_z':'Absolute tool Z for horizontal transfers; must be above every station approach Z.',
            'tool_r':'Rotation about vertical Z, applied at every station; it does not tilt the electrode.',
            'position_tolerance':'Maximum XYZ distance error accepted after queue completion.',
            'rotation_tolerance':'Maximum R angle error accepted after queue completion.',
        }.items(): self.fields[key].setToolTip(tip)
        robot.addWidget(self.settings_group('Hardware batch readiness', [('calibrated','Station poses and paths calibrated'),('fixture_verified','Gripper, seating and dry contact verified')]))
        robot.addWidget(self.note('Default coordinates and workspace bounds are placeholders. Position feedback verifies arm pose, not successful pickup or electrical contact. No automatic retry is enabled.')); robot.addStretch()
        bounds,self.workspace_feedback,self.workspace_diagram,self.workspace_scroll=self.calibration_tab('Workspace')
        bounds.addWidget(self.note('These bounds constrain commanded endpoints. They do not model obstacles, joint limits or collision-free paths. Validate the complete travel route in the lab.'))
        bounds.addWidget(self.settings_group('Cartesian bounds (mm)', [(f'workspace_{axis}_{end}',f'{axis.upper()} {end}',-400,400) for axis in 'xyz' for end in ('min','max')]))
        bounds.addWidget(self.settings_group('Radial bounds from base (mm)', [('workspace_radius_min','Minimum radius',0,400),('workspace_radius_max','Maximum radius',1,400)]))
        bounds.addWidget(self.settings_group('Rinse footprint (mm)', [('rinse_beaker_diameter','Rinse beaker diameter',10,250)]))
        bounds.addWidget(self.settings_group('Controller reachability and fault detection', [('controller_preflight','Check controller pose limits before movement'),('reachability_step','Route sample spacing (mm)',1,50),('motion_stall_timeout','No-progress timeout (s)',1,60)]))
        self.map_feedback=self.note('No controller workspace map applied.')
        bounds.addWidget(self.map_feedback)
        mapped=QHBoxLayout(); self.fit_rack_button=button('Fit rack within mapped workspace…',self.preview_rack_fit)
        self.clear_map_button=button('Remove saved map',self.clear_workspace_map)
        mapped.addWidget(self.fit_rack_button); mapped.addWidget(self.clear_map_button); bounds.addLayout(mapped)
        self.route_check=button('Check planned route · no movement',lambda:self.submit('check_route')); bounds.addWidget(self.route_check)
        bounds.addWidget(button('Workspace explorer…',self.open_workspace_explorer))
        bounds.addWidget(self.note('Connected/homed Hardware robot required. Asks DobotLink CheckPoseLimit about XYZ/R at station heights, Travel Z and sampled straight transfers. This detects supported controller limits, not obstacles or full collision clearance. Unsupported firmware blocks this check; disabling it explicitly leaves configured bounds, alarm monitoring and the progress watchdog. A passed check applies only to that settings snapshot.'))
        bounds.addStretch()
        cell=self.settings_tab('Cell & carrier'); row=QHBoxLayout()
        row.addWidget(self.settings_group('Beaker & cap (mm)', [('beaker_diameter','Body diameter'),('beaker_height','Beaker height'),('rim_diameter','Measured rim diameter'),('cap_clearance','Diametral clearance'),('cap_wall','Skirt wall'),('cap_thickness','Plate thickness'),('skirt_depth','Skirt depth'),('re_hole','RE opening'),('ce_hole','CE opening'),('port_offset','RE/CE offset')]))
        row.addWidget(self.settings_group('Carrier & guide (mm)', [('rod_diameter','Rod diameter'),('rod_length','Rod length'),('shoulder_diameter','Shoulder diameter'),('tip_below_shoulder','Tip below shoulder'),('immersion','Target immersion'),('we_clearance','WE clearance'),('funnel_diameter','Guide mouth')]))
        cell.addLayout(row); self.sketch=CapSketch(self.s); cell.addWidget(self.sketch)
        ca=QHBoxLayout(); ca.addWidget(button('Update sketch',self.update_sketch)); ca.addWidget(button('Export STL + OpenSCAD…',self.export_cap,True)); ca.addStretch(); cell.addLayout(ca)
        cell.addWidget(self.note('Nominal 100 mL beaker: Ø50 × 70 mm. Measure its rim before printing. The cap is vented; RE/CE collars, dry contacts and custom gripper remain separate parts.'))
        rack,self.rack_feedback,self.rack_diagram,self.rack_scroll=self.calibration_tab('Rack design',RackDiagram)
        design=QGroupBox('Rack construction'); rf=QFormLayout(design)
        self.combo_field(rf,'rack_design','Design',[('Legacy blind rod sockets','socket'),('Modular holder-supported lattice','lattice')]); rack.addWidget(design)
        self.rack_export=button('Export rack printing files…',self.export_rack); rack.addWidget(self.rack_export)
        self.lattice_preset=button('Use lattice and allow holder spacing',self.use_lattice,True); rack.addWidget(self.lattice_preset)
        rack.addWidget(self.note('Uses batch slot range, columns, XY coordinates and rectangular/radial layout from Experiment and Robot calibration. Complete rows are exported. The spacing button only widens pitch/angle as needed; it commands no motion and clears readiness.'))
        self.holder_group=self.settings_group('Pickup holder (mm)', [('holder_diameter','Grip body diameter',10,60),('holder_height','Grip body height',8,60),('holder_flange_diameter','Upper flange diameter',12,80),('holder_flange_thickness','Flange thickness',2,15),('holder_rod_depth','Rod socket depth',3,55),('holder_rod_clearance','Rod diametral clearance',.1,2),('holder_pad_diameter','Contact-pad recess diameter',2,30),('holder_pad_depth','Contact-pad recess depth',.2,8),('holder_wire_diameter','Wire passage diameter',.5,8),('holder_set_screw_diameter','Set-screw pilot diameter',1,6)])
        rack.addWidget(self.holder_group)
        self.lattice_group=self.settings_group('Top support and free-hanging rod (mm)', [('rack_holder_clearance','Holder recess clearance',.1,3),('rack_seat_depth','Holder locating depth',.5,10),('rack_deck_thickness','Top thickness',4,20),('rack_seat_wall','Seat outer wall',2,10),('rack_rib_width','Connecting rib width',4,20),('rack_hanging_length','Rod below holder bottom',5,200),('rack_tip_clearance','Tip clearance above bench',5,50),('rack_gripper_gap','Extra gap beyond flange',2,50)])
        rack.addWidget(self.lattice_group)
        self.module_group=self.settings_group('Reusable parts and printer', [('rack_module_slots','Maximum slots per top module',1,12),('rack_peg_diameter','Foot peg diameter (mm)',3,8),('rack_peg_clearance','Peg socket clearance (mm)',.1,1.5),('rack_peg_length','Peg insertion length (mm)',1,6),('rack_foot_base','Foot base thickness (mm)',2,10),('rack_foot_column_diameter','Foot column diameter (mm)',6,16),('rack_foot_mount_hole','Foot fixing hole (mm)',2,4),('rack_printer_width','Printer usable width (mm)',40,500),('rack_printer_depth','Printer usable depth (mm)',40,500)])
        rack.addWidget(self.module_group)
        rack.addWidget(self.note('Hanging length must cover the rod length (Cell & carrier) minus its insertion into the holder, plus any extra active-tip projection. Top modules, identical fork feet and pickup holders are separate STL files with quantities and assembly coordinates. Pegs are provisional removable push fits; secure each independent module to the bench. Reuse full modules when coordinates, holder dimensions and module size stay unchanged; changed partial modules may need reprinting. Print a fit trial first. Metal contact, wire and rod-retention screw are separate parts.'))
        self.socket_group=self.settings_group('Legacy blind-socket rack (mm)', [('rack_socket_clearance','Socket diametral clearance',.1,3),('rack_socket_depth','Blind socket depth',1,200),('rack_post_height','Socket post height',2,250),('rack_socket_wall','Socket wall thickness',2,20),('rack_base_thickness','Base thickness',2,30),('rack_margin','Base edge margin',1,30)])
        rack.addWidget(self.socket_group)
        rack.addWidget(self.note('Changing the holder does not redesign the cell cap or electrical probe bracket. Confirm compatibility before printing. Physical seat height does not set robot gripping Z; teach Z after assembly.')); rack.addStretch()

    def use_lattice(self):
        from dataclasses import replace
        import math
        s=replace(self.read_settings(validate=False),rack_design='lattice',calibrated=False,fixture_verified=False)
        separation=s.lattice_dimensions()['separation']+.5
        s.rack_pitch=max(s.rack_pitch,separation)
        if s.rack_layout=='radial':
            if separation>=2*s.rack_radius:
                self.statusBar().showMessage('Rack radius is too small for holder spacing'); return
            s.rack_angle_step=max(s.rack_angle_step,math.degrees(2*math.asin(separation/(2*s.rack_radius))))
        self.apply_settings(s)
        self.statusBar().showMessage('Lattice selected; spacing widened if needed. No movement commanded. Check workspace and teach rack Z after assembly.')

    def submit(self,command,payload=None):
        if self.busy or self._close_pending: return
        try: s=self.read_settings(validate=command not in ('rehearsal_pose','workspace_scan'))
        except Exception as exc: QMessageBox.warning(self,'Check settings',str(exc)); return
        self.active_command=command; self.busy=True; self.refresh_controls(); self.statusBar().showMessage(command.replace('_',' ').capitalize()+'…')
        self.worker.submit(command,s,payload)
    def open_workspace_explorer(self):
        from .workspace_explorer import WorkspaceExplorer
        settings=self.read_settings(validate=False)
        if self.workspace_explorer is None:
            self.workspace_explorer=WorkspaceExplorer(self,settings)
            self.workspace_explorer.scan_requested.connect(self.start_workspace_scan)
            self.workspace_explorer.cancel_requested.connect(self.cancel_workspace_scan)
            self.workspace_explorer.target_selected.connect(self.copy_workspace_target)
            self.workspace_explorer.workspace_selected.connect(self.apply_workspace_map)
        if not self.workspace_explorer.data and settings.workspace_map:
            self.workspace_explorer.display_map(settings.workspace_map)
        self.workspace_explorer.settings=settings
        self.refresh_controls(); self.workspace_explorer.show(); self.workspace_explorer.raise_()
    def apply_workspace_map(self,data):
        if self.busy: return
        from copy import deepcopy
        from dataclasses import replace
        from .workspace_map import Envelope
        s=self.read_settings(validate=False)
        low=min(s.rack_z,s.cell_z,s.rinse_z); high=s.safe_z
        try:
            envelope=Envelope(data); xmin,xmax,ymin,ymax=envelope.rectangle(low,high,s.tool_r)
            if low>=high: raise ValueError('Travel Z must be above the station heights.')
        except (ValueError,KeyError,TypeError) as exc:
            QMessageBox.warning(self,'Workspace cannot be applied',str(exc)); return
        text=(f'Current experiment Z span: {low:g} to {high:g} mm, R {s.tool_r:g}°.\n'
              f'Proposed X bounds: {xmin:g} to {xmax:g}; Y: {ymin:g} to {ymax:g} mm.\n'
              'Save the full map and replace XYZ bounds with this rectangle and Z span? '
              'Radial bounds stay in effect. Rack/cell/rinse positions and Travel Z are unchanged.\n'
              'The rectangle groups accepted corner samples; its interior is untested. '
              'Historical maps require rechecking on current hardware. No movement will occur.')
        if QMessageBox.question(self,'Use controller workspace',text)!=QMessageBox.StandardButton.Yes: return
        self.apply_settings(replace(s,workspace_map=deepcopy(data),workspace_x_min=xmin,workspace_x_max=xmax,
            workspace_y_min=ymin,workspace_y_max=ymax,workspace_z_min=low,workspace_z_max=high,
            calibrated=False,fixture_verified=False))
        self.workspace_explorer.settings=self.read_settings(validate=False); self.workspace_explorer.plot.update()
        self.statusBar().showMessage('Workspace applied to this profile. Save configuration to persist it; station positions still need review.')
    def clear_workspace_map(self):
        if self.busy: return
        from dataclasses import replace
        self.apply_settings(replace(self.read_settings(validate=False),workspace_map={},calibrated=False,fixture_verified=False))
        self.statusBar().showMessage('Saved map removed; numerical bounds retained.')
    def preview_rack_fit(self):
        if self.busy: return
        from .workspace_map import fit_rack
        from dataclasses import replace
        s=self.read_settings(validate=False)
        try: proposed=fit_rack(s,s.workspace_map)
        except (ValueError,KeyError,TypeError) as exc:
            QMessageBox.warning(self,'Rack placement',str(exc)); return
        keys=('rack_radius','rack_start_angle') if s.rack_layout=='radial' else ('rack_x','rack_y')
        changes='\n'.join(f'{key}: {getattr(s,key):g} → {getattr(proposed,key):g}' for key in keys)
        if QMessageBox.question(self,'Preview rack placement',changes+'\nPreserves spacing and layout; checks all exported slots against surrounding map samples and numerical bounds. Cell/rinse positions stay fixed.\nApply without moving? Physical clearance and current controller route still need checking.')==QMessageBox.StandardButton.Yes:
            self.apply_settings(replace(proposed,calibrated=False,fixture_verified=False))
    def update_map_feedback(self,s):
        if not hasattr(self,'map_feedback'): return
        self.fit_rack_button.setEnabled(not self.busy and bool(s.workspace_map))
        self.clear_map_button.setEnabled(not self.busy and bool(s.workspace_map))
        if not s.workspace_map:
            self.map_feedback.setText('No controller map applied. Open Workspace explorer to scan or load one.'); return
        from .workspace_map import Envelope
        try:
            envelope=Envelope(s.workspace_map); low=min(s.rack_z,s.cell_z,s.rinse_z)
            groups={True:[],False:[],None:[]}
            stations=[(f'Rack {i}',s.rack_pose(i)) for i in range(s.first_electrode,min(101,s.first_electrode+s.electrodes))]
            stations += [('Cell',(s.cell_x,s.cell_y,s.cell_z)),('Rinse',(s.rinse_x,s.rinse_y,s.rinse_z))]
            for label,pose in stations: groups[envelope.status(*pose[:2],low,s.safe_z,s.tool_r)].append(label)
            lines=[f'Saved controller map: {s.workspace_map.get("started_utc","unknown date")} · required Z {low:g}…{s.safe_z:g}, R {s.tool_r:g}°']
            for state,label in ((True,'Supported by surrounding samples'),(False,'Rejected supporting samples'),(None,'Unknown: outside scan, missing samples or different R')):
                if groups[state]: lines.append(label+': '+', '.join(groups[state]))
            lines.append('Planning feedback only; green interiors are untested. Recheck the current controller route; no obstacle model.')
            self.map_feedback.setText('\n'.join(lines))
        except (ValueError,KeyError,TypeError) as exc: self.map_feedback.setText('Invalid saved workspace map: '+str(exc))
    def start_workspace_scan(self,spec):
        self.submit('workspace_scan',spec)
        if self.active_command!='workspace_scan':
            self.workspace_explorer.scanning=False; self.workspace_explorer.update_buttons()
    def cancel_workspace_scan(self):
        if self.busy and self.active_command=='workspace_scan': self.worker.cancel()
    def on_workspace_sample(self,event):
        if self.workspace_explorer: self.workspace_explorer.handle_event(event)
    def copy_workspace_target(self,pose):
        for field,value in zip(self.target_fields,pose): field.setValue(value)
        self.statusBar().showMessage('Workspace pose copied to Manual robot target. No movement commanded.')
    def disconnect_devices(self):
        if self.mode.currentData()=='hardware' and self.device_state.get('holding'):
            self.statusBar().showMessage('Secure the electrode and open the gripper before disconnecting; disconnect turns off its pump.')
            return
        self.submit('disconnect')
    def change_mode(self):
        self.current_pose=None
        for diagram in (self.calibration_diagram,self.workspace_diagram,self.experiment_tracker,self.manual_tracker): diagram.set_pose(None)
        self.device_state={'robot':False,'potentiostat':False,'homed':False,'holding':False}
        hardware=self.mode.currentData()=='hardware'; self.plot.synthetic=not hardware; self.plot.clear()
        self.badge.setText('● HARDWARE' if hardware else '● SIMULATION'); self.sidebar_status.setText('Hardware\nPhysical devices selected' if hardware else 'Simulation\nNo physical commands')
        self.mode_note.setText('Hardware mode · connect devices, home the robot, and verify calibration before a batch. Stop is a software queue stop, not a physical emergency stop.' if hardware else 'Simulation mode · synthetic CV data. Connect a real camera independently if desired.')
        self.submit('configure')
    def on_devices(self,state):
        self.device_state=state
        if not state['robot']:
            self.current_pose=None
            for diagram in (self.calibration_diagram,self.workspace_diagram,self.experiment_tracker,self.manual_tracker): diagram.set_pose(None)
        hardware=self.mode.currentData()=='hardware'
        self.robot_status.setText('Robot · '+('connected' if state['robot'] else 'disconnected')+(' · homed' if state['homed'] else ''))
        self.pot_status.setText('Potentiostat · '+state.get('potentiostat_name','Disconnected'))
        gripper_labels={'closed':'closed · pump on / electrode may be held','released':'released · pump off','fully_open':'fully open · pump on','unknown':'unknown'}
        self.grip_label.setText('Commanded state: '+gripper_labels[state.get('gripper_state','unknown')]+'. No pickup sensor is configured.')
        self.refresh_controls()
    def on_diagnostic(self,data):
        previous=self.robot_diagnostics.get('fault','').split('\n')[0]
        self.robot_diagnostics=dict(data)
        fault=data.get('fault','')
        if fault and fault.split('\n')[0]!=previous: self.log.appendPlainText('Robot: '+fault)
        if fault and not self.running_batch: self.state.setText('Robot fault')
        elif previous and not self.running_batch: self.state.setText('Ready')
        self.update_diagnostic_labels()
        if fault:
            for label in (self.calibration_feedback,self.workspace_feedback):
                label.setText('Robot check: '+fault); label.setStyleSheet('color: #b53636;')
        elif previous: self.update_calibration_feedback(invalidate=False)
        self.refresh_controls()
    def update_diagnostic_labels(self):
        d=self.robot_diagnostics
        def xyz(p): return ', '.join(f'{p[k]:.2f}' for k in ('x','y','z')) if p else '—'
        fault=bool(d.get('fault'))
        text=('ROBOT FAULT · open details\n' if fault else '')+'Target XYZ: '+xyz(d.get('target'))+'\nReported XYZ: '+xyz(d.get('actual'))
        text+='\n'+str(d.get('preflight','Checks not yet run'))
        if str(d.get('alarm_monitor','')).startswith('unavailable'): text+='\nAlarm feedback unavailable — details'
        for label in (self.experiment_diagnostic,self.manual_diagnostic):
            label.setText(text); label.setStyleSheet('color: #a42b2b; background: #fff0ed; padding: 4px; font-size: 11px;' if fault else 'font-size: 11px;')
    def show_robot_diagnostics(self):
        d=self.robot_diagnostics
        report=json.dumps(d,indent=2) if d else 'No controller diagnostics yet. Connect the robot and use Check planned route.'
        dialog=QMessageBox(self); dialog.setWindowTitle('Robot diagnostics — target, reported pose and faults')
        dialog.setText(d.get('fault') or d.get('preflight','Controller checks not yet run'))
        dialog.setInformativeText('Coordinates are reported tool XYZ/R. An alarm or stalled move requires inspection; clearing alarms does not home or resume the route.')
        dialog.setDetailedText(report)
        copy=dialog.addButton('Copy diagnostic report',QMessageBox.ButtonRole.ActionRole)
        copy.clicked.connect(lambda:QApplication.clipboard().setText(report))
        dialog.addButton(QMessageBox.StandardButton.Close); dialog.exec()
    def refresh_controls(self):
        idle=not self.busy and not self._close_pending; hardware=self.mode.currentData()=='hardware'; d=self.device_state
        self.mode.setEnabled(idle and not d.get('robot') and not d.get('potentiostat') or idle and self.mode.currentData()=='simulation')
        # Switching modes owns teardown in the worker; hardware users disconnect first.
        ready=not getattr(self,'validation_issues',[]) and (not hardware or (not self.robot_diagnostics.get('fault') and d.get('homed',False) and self.fields['calibrated'].isChecked() and self.fields['fixture_verified'].isChecked()))
        self.preset_button.setEnabled(idle and d.get('robot',False) and not d.get('holding',False) and (not hardware or d.get('homed',False)))
        self.start.setEnabled(idle and ready and not d.get('holding',False) and d.get('robot',False) and d.get('potentiostat',False))
        self.start.setToolTip('Hardware: connect both devices, home the robot, and verify calibration and the fixture in Settings.')
        self.rehearse.setEnabled(idle and ready and not d.get('holding',False) and d.get('robot',False))
        self.rehearse.setToolTip('Run pickup, release in cell, rinse and return with the gripper active; no potentiostat required. Uses settling time as the brief cell wait.')
        self.pause.setEnabled(self.running_batch and not hardware and not self._close_pending)
        self.stop.setEnabled(self.busy); self.manual_stop.setEnabled(self.busy or idle and d.get('robot',False))
        self.connect_robot.setEnabled(idle and not d.get('robot',False)); self.connect_pot.setEnabled(idle and not d.get('potentiostat',False)); self.disconnect.setEnabled(idle and (d.get('robot',False) or d.get('potentiostat',False)))
        for key in ('robot_port','robot_host','robot_ws_port','robot_timeout'):
            self.fields[key].setEnabled(idle and not d.get('robot',False))
        self.fields['potentiostat_id'].setEnabled(idle and not d.get('potentiostat',False))
        radial=self.fields['rack_layout'].currentData()=='radial'
        for key in ('rack_radius','rack_start_angle','rack_angle_step'): self.fields[key].setEnabled(idle and radial)
        for key in ('rack_x','rack_y'): self.fields[key].setEnabled(idle and not radial)
        self.placement_export.setEnabled(idle); self.rack_export.setEnabled(idle)
        self.lattice_preset.setEnabled(idle)
        self.update_map_feedback(self.read_settings(validate=False))
        can_check=idle and hardware and d.get('robot',False) and d.get('homed',False)
        if self.workspace_explorer: self.workspace_explorer.set_available(can_check)
        self.route_check.setEnabled(can_check); self.manual_route_check.setEnabled(can_check)
        self.alarm_clear.setEnabled(idle and hardware and d.get('robot',False))
        lattice=self.fields['rack_design'].currentData()=='lattice'
        for group in (self.holder_group,self.lattice_group,self.module_group):
            group.setEnabled(idle and lattice); group.setVisible(lattice)
        self.socket_group.setEnabled(idle and not lattice); self.socket_group.setVisible(not lattice)
        self.setup_box.setEnabled(idle); self.settings_tabs.setEnabled(idle); self.save_button.setEnabled(idle); self.load_button.setEnabled(idle)
        for b in self.manual_buttons: b.setEnabled(idle and d.get('robot',False))
        for b in self.motion_buttons: b.setEnabled(idle and d.get('robot',False) and (not hardware or d.get('homed',False)))
        self.teach_button.setEnabled(idle and self.current_pose is not None and d.get('robot',False) and (not hardware or d.get('homed',False)))
    def prepare_queue(self):
        if self.running_batch: return
        first=self.fields['first_electrode'].value(); count=self.fields['electrodes'].value()
        self.queue_table.setRowCount(count)
        for row,index in enumerate(range(first,first+count)):
            for col,text in enumerate((str(index),f'WE {index:02d}','Queued')):
                self.queue_table.setItem(row,col,QTableWidgetItem(text))
    def start_run(self,rehearsal=False):
        if self.busy: return
        try:
            s=self.read_settings().validate_batch()
            if s.mode=='hardware' and not self.device_state.get('homed'): raise ValueError('Home the robot on Manual robot before a hardware batch')
            if self.device_state.get('holding'): raise ValueError('Release or secure the currently held electrode before starting a new batch')
        except Exception as exc: QMessageBox.warning(self,'Batch not ready',str(exc)); return
        self.s=s
        for tracker in (self.experiment_tracker,self.manual_tracker): tracker.clear_trail()
        self.plot.clear(); self.plot.synthetic=s.mode=='simulation'; self.plot_selection.clear(); self.plot_selection.addItem('All electrodes',None)
        self.queue_table.setRowCount(s.electrodes)
        for row,index in enumerate(range(s.first_electrode,s.first_electrode+s.electrodes)):
            self.plot_selection.addItem(f'Electrode {index}',index)
            for col,text in enumerate((str(index),f'WE {index:02d}','Queued')): self.queue_table.setItem(row,col,QTableWidgetItem(text))
        self.plot.update(); self.log.clear(); self.progress.setRange(0,s.electrodes); self.progress.setValue(0)
        self.running_batch=True; self.paused=False; self.pause.setText('Pause'); self.state.setText('Starting…'); self.submit('rehearse' if rehearsal else 'run')
    def select_plot(self):
        if hasattr(self,'plot'): self.plot.selected=self.plot_selection.currentData(); self.plot.update()
    def on_event(self,event):
        index=event['electrode']; self.state.setText(f"WE {index} · {event['state'].capitalize()}" if index else event['state'].capitalize())
        self.log.appendPlainText(f"{event['time'][11:19]}  {event['detail']}")
        if index is not None:
            row=index-self.s.first_electrode
            if 0<=row<self.queue_table.rowCount(): self.queue_table.setItem(row,2,QTableWidgetItem(event['state'].capitalize()))
        if event['state']=='done': self.progress.setValue(index-self.s.first_electrode+1)
    def on_result(self,folder,status):
        self.output=Path(folder) if folder else None; self.state.setText(status.capitalize()); self.statusBar().showMessage(f'Run {status} · {folder}')
    def on_completed(self,command,ok,message):
        if command=='shutdown': self.statusBar().showMessage(message); return
        self.busy=False; self.active_command=None
        if command=='workspace_scan' and self.workspace_explorer:
            self.workspace_explorer.scanning=False; self.workspace_explorer.update_buttons()
            if not ok: self.workspace_explorer.status.setText(message+' · unqueried points remain unknown')
        if command in ('run','rehearse'): self.running_batch=False
        if not ok:
            self.log.appendPlainText(message); self.statusBar().showMessage(message)
            if command in ('run','rehearse'): self.state.setText('Stopped' if message=='Stopped' else 'Failed')
            if not self._close_pending and message!='Stopped': QMessageBox.warning(self,'Device operation stopped',message)
        elif command not in ('run','rehearse'): self.statusBar().showMessage(command.replace('_',' ').capitalize()+' completed')
        if command=='rehearsal_pose' and ok:
            self.apply_compact_rehearsal(self.current_pose)
        self.refresh_controls()
    def on_pose(self,pose):
        if not all(k in pose for k in ('x','y','z','r')):
            self.current_pose=None; self.pose_label.setText('Position unavailable')
            for diagram in (self.calibration_diagram,self.workspace_diagram,self.experiment_tracker,self.manual_tracker): diagram.set_pose(None)
            return
        self.current_pose=dict(pose)
        for diagram in (self.calibration_diagram,self.workspace_diagram,self.experiment_tracker,self.manual_tracker): diagram.set_pose(pose)
        self.pose_label.setText('    '.join(f'{k.upper()} {pose[k]:.2f}' for k in ('x','y','z','r')))
    def pause_run(self):
        if not self.running_batch or self.mode.currentData()!='simulation': return
        self.paused=not self.paused
        self.worker.control.resume.clear() if self.paused else self.worker.control.resume.set()
        self.pause.setText('Resume' if self.paused else 'Pause'); self.state.setText('Paused' if self.paused else 'Resuming…')
    def stop_run(self):
        if self.busy:
            self.worker.cancel(); self.pause.setEnabled(False); self.stop.setEnabled(False); self.state.setText('Stopping…')
        else: self.submit('stop')
    def teach_pose(self):
        if self.current_pose is None: return
        station=self.teach_station.currentIndex()
        if station==3: self.fields['safe_z'].setValue(self.current_pose['z'])
        else:
            prefix=('rack','cell','rinse')[station]
            if station==0 and self.fields['rack_layout'].currentData()=='radial':
                import math
                self.fields['rack_radius'].setValue(math.hypot(self.current_pose['x'],self.current_pose['y']))
                self.fields['rack_start_angle'].setValue(math.degrees(math.atan2(self.current_pose['y'],self.current_pose['x'])))
                self.fields['rack_z'].setValue(self.current_pose['z'])
            else:
                for axis in 'xyz': self.fields[f'{prefix}_{axis}'].setValue(self.current_pose[axis])
            self.fields['tool_r'].setValue(self.current_pose['r'])
        self.fields['calibrated'].setChecked(False); self.statusBar().showMessage('Pose copied to Settings; verify the travel route before marking calibrated')
    def open_output(self):
        path=self.output or ROOT/'runs'; path.mkdir(exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def camera_buttons_update(self):
        active=self.camera is not None and self.camera.isRunning()
        self.connect_camera.setEnabled(not active and not self._close_pending); self.disconnect_camera.setEnabled(active and not self._close_pending); self.snapshot.setEnabled(self.last_frame is not None)
    def camera_connect(self):
        if self.camera and self.camera.isRunning(): return
        self.last_frame=None; self.camera_status.setText('Searching…')
        self.camera=CameraWorker(self.fields['camera_index'].value()); self.camera.frame.connect(self.on_frame); self.camera.status.connect(self.camera_status.setText)
        self.camera.finished.connect(self.camera_finished); self.camera.start(); self.camera_buttons_update()
    def camera_disconnect(self):
        if self.camera: self.camera.requestInterruption()
        self.disconnect_camera.setEnabled(False); self.camera_status.setText('Disconnecting…')
    def camera_finished(self):
        self.camera_buttons_update()
        if self.camera_status.text()=='Disconnecting…': self.camera_status.setText('Disconnected')
        if self._close_pending: self.close()
    def on_frame(self,image):
        self.last_frame=image; self.snapshot.setEnabled(True); self.update_preview()
    def update_preview(self):
        if self.last_frame is not None:
            self.preview.set_frame(self.last_frame)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'preview'): self.update_preview()
    def camera_snapshot(self):
        if self.last_frame is None: return
        (ROOT/'runs').mkdir(exist_ok=True)
        name,_=QFileDialog.getSaveFileName(self,'Save camera snapshot',str(ROOT/'runs'/'camera.png'),'PNG (*.png)')
        if name and not self.last_frame.save(name): QMessageBox.warning(self,'Snapshot failed','Could not write image')
    def update_sketch(self):
        try: self.sketch.s=self.read_settings(); self.sketch.update()
        except Exception as exc: QMessageBox.warning(self,'Check geometry',str(exc))
    def export_placement(self):
        try: s=self.read_settings()
        except Exception as exc: QMessageBox.warning(self,'Check settings',str(exc)); return
        name,_=QFileDialog.getSaveFileName(self,'Export placement guide',str(ROOT/'cad'/'placement-guide.pdf'),'PDF (*.pdf)')
        if name:
            try:
                from .placement_pdf import export_placement_pdf
                export_placement_pdf(s,name); self.statusBar().showMessage('Placement PDF exported: '+name)
            except Exception as exc: QMessageBox.warning(self,'PDF export failed',str(exc))

    def export_rack(self):
        try: s=self.read_settings()
        except Exception as exc: QMessageBox.warning(self,'Check rack geometry',str(exc)); return
        folder=QFileDialog.getExistingDirectory(self,'Choose rack export folder',str(ROOT/'cad'))
        if folder:
            try:
                from .rack_cad import export_rack
                path=export_rack(s,folder); meta=json.loads(Path(folder,'rack_manifest.json').read_text())
                if s.rack_design=='lattice':
                    self.statusBar().showMessage(f'Modular rack exported: {len(meta["modules"])} top modules, {meta["foot_quantity"]} identical feet, {meta["holder_quantity"]} holders. See ASSEMBLY.md and rack_manifest.json; teach rack Z.')
                else:
                    size=[b-a for a,b in zip(*meta['bounds_mm'])]
                    self.statusBar().showMessage(f'Rack exported: {path} | {size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm; check printer bed and teach rack Z.')
            except Exception as exc: QMessageBox.warning(self,'Rack export failed',str(exc))

    def export_cap(self):
        try: s=self.read_settings()
        except Exception as exc: QMessageBox.warning(self,'Check geometry',str(exc)); return
        folder=QFileDialog.getExistingDirectory(self,'Choose cap export folder',str(ROOT/'cad'))
        if folder:
            try:
                from .cad import export_cap
                path=export_cap(s,folder); Path(folder,'cap_settings.json').write_text(json.dumps(asdict(s),indent=2)); self.statusBar().showMessage(f'Cap exported to {path}')
            except Exception as exc: QMessageBox.warning(self,'Export failed',str(exc))
    def on_worker_finished(self):
        if self._close_pending: self.close()
    def closeEvent(self,event):
        if self.mode.currentData()=='hardware' and not self._close_pending:
            if self.busy:
                self.stop_run(); self.statusBar().showMessage('Stop requested. Recover any electrode before closing the app.'); event.ignore(); return
            if self.device_state.get('holding'):
                self.statusBar().showMessage('Secure the electrode and open the gripper before closing; closing turns off its pump.'); event.ignore(); return
        device_running=self.worker.isRunning(); camera_running=self.camera is not None and self.camera.isRunning()
        if device_running or camera_running:
            self._close_pending=True
            if not self._shutdown_sent:
                self._shutdown_sent=True; self.worker.shutdown()
            if camera_running: self.camera_disconnect()
            self.refresh_controls(); self.statusBar().showMessage('Stopping and disconnecting devices before closing…'); event.ignore()
        else: event.accept()

def main():
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=Window(); window.show(); sys.exit(app.exec())

if __name__=='__main__': main()
