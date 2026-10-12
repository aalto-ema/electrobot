import sys,time,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtGui import QImage,QColor
from electrobot.app import Window,STYLE
warnings=[]
QMessageBox.warning=lambda *args: warnings.append(args[-1])
app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
w=Window(); w.show()
def idle(timeout=10):
    deadline=time.monotonic()+timeout
    while w.busy and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    app.processEvents(); assert not w.busy,'Device command did not complete'
idle()
assert 'pypalmsens' not in sys.modules and 'dobotkit' not in sys.modules
assert w.read_settings().electrodes==3
assert w.fields['scan_rate'].isVisible()
assert w.preview.isVisible()
assert w.calibration_diagram.workspace and w.workspace_diagram.workspace
assert not w.fields['rack_pitch'].isVisible()
for i in range(3):
    w.nav.setCurrentRow(i); app.processEvents(); w.grab().save(str(Path('cad')/f'ui-{i}.png'))
for index in range(w.settings_tabs.count()):
    w.settings_tabs.setCurrentIndex(index); app.processEvents()
    w.grab().save(f'cad/ui-settings-{index}.png')
for index,scroll,diagram in ((2,w.calibration_scroll,w.calibration_diagram),(3,w.workspace_scroll,w.workspace_diagram)):
    w.settings_tabs.setCurrentIndex(index); app.processEvents()
    diagram_top=diagram.mapTo(w,diagram.rect().topLeft())
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()); app.processEvents()
    assert diagram.isVisible() and diagram.mapTo(w,diagram.rect().topLeft())==diagram_top
    assert diagram.visibleRegion().boundingRect()==diagram.rect()
    w.grab().save(f'cad/ui-settings-{index}-scrolled.png')
    scroll.verticalScrollBar().setValue(0)
w.nav.setCurrentRow(1); w.submit('jog',(0,1)); idle(); assert w.current_pose['x']==201
assert w.experiment_tracker.pose==w.current_pose==w.manual_tracker.pose
assert any(200<p['x']<201 for p in w.manual_tracker.trail)
assert w.calibration_diagram.pose==w.current_pose==w.workspace_diagram.pose
w.submit('grip',True); idle(); assert w.device_state['holding']
w.submit('grip',False); idle(); assert not w.device_state['holding']
w.submit('move',(201,-65,15,0)); idle()
w.teach_station.setCurrentIndex(0); w.teach_pose(); assert w.fields['rack_x'].value()==201
assert not w.fields['calibrated'].isChecked()
w.nav.setCurrentRow(0); w.fields['electrodes'].setValue(3); w.fields['first_electrode'].setValue(2)
w.fields['simulation_speed'].setValue(100); w.fields['cycles'].setValue(1)
image=QImage(640,360,QImage.Format.Format_RGB32); image.fill(QColor('#253f4b')); w.on_frame(image); w.camera_status.setText('Test image · camera disconnected')
w.start_run(); idle()
assert w.progress.value()==3 and w.state.text()=='Completed'
assert w.start.isEnabled() and len(w.plot.data[2])>0 and set(w.plot.data)=={2,3,4}
assert w.queue_table.item(2,2).text()=='Done'
w.grab().save('cad/ui-run.png')
w.resize(1280,900); app.processEvents(); w.grab().save('cad/ui-compact.png')
assert w.width()<=1280 and w.height()<=900,(w.width(),w.height())
w.resize(1440,960); app.processEvents()
w.fields['simulation_speed'].setValue(1); w.start_run(); w.pause_run(); assert w.paused
w.stop_run(); idle(); assert w.state.text()=='Stopped'
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'settings.json'
    import electrobot.app as module
    with patch.object(module,'ROOT',Path(d)): w.save()
    config=json.loads(path.read_text()); assert config['first_electrode']==2
    w.fields['electrodes'].setValue(1)
    with patch.object(module.QFileDialog,'getOpenFileName',return_value=(str(path),'JSON')): w.load()
    assert w.fields['electrodes'].value()==3
    w.fields['rack_layout'].setCurrentIndex(1)
    assert w.read_settings().rack_layout=='radial'
    assert not w.fields['rack_x'].isEnabled() and w.fields['rack_radius'].isEnabled()
    import math
    w.teach_station.setCurrentIndex(0); w.teach_pose()
    assert abs(w.fields['rack_radius'].value()-math.hypot(w.current_pose['x'],w.current_pose['y']))<.01
    w.fields['safe_z'].setValue(w.current_pose['z']+5)
    w.nav.setCurrentRow(2); w.settings_tabs.setCurrentIndex(2); app.processEvents()
    w.grab().save('cad/ui-radial-settings.png')
    with patch.object(module.QFileDialog,'getSaveFileName',return_value=(str(Path(d)/'placement.pdf'),'PDF')): w.export_placement()
    assert Path(d,'placement.pdf').read_bytes().startswith(b'%PDF')
    with patch.object(module.QFileDialog,'getExistingDirectory',return_value=d): w.export_rack()
    assert Path(d,'electrode_rack.stl').exists() and Path(d,'rack_manifest.json').exists()
    w.fields['rack_layout'].setCurrentIndex(0); w.nav.setCurrentRow(0)
# Hardware mode must not implicitly connect, home or move either device.
w.mode.setCurrentIndex(1); idle(); assert not w.device_state['robot'] and not w.device_state['potentiostat']
assert not w.start.isEnabled() and not w.device_state['homed']
w.grab().save('cad/ui-hardware.png')
w.mode.setCurrentIndex(0); idle()
w.close(); deadline=time.monotonic()+3
while w.worker.isRunning() and time.monotonic()<deadline:
    app.processEvents(); time.sleep(.01)
app.processEvents(); assert not w.worker.isRunning()
assert not warnings,warnings
print('UI: layout, shared camera, manual jog/grip/teach, batch, pause/stop, profile roundtrip, mode isolation and shutdown passed')
