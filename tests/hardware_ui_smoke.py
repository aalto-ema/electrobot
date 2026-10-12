"""Exercise real adapter/worker/UI wiring using doubles, never physical devices."""
import sys,time,json,tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication,QMessageBox
from electrobot.app import Window,STYLE
from electrobot.drivers import DobotRobot,PalmSensPotentiostat
from test_drivers import FakeArm,FakeSDK
import electrobot.worker as worker_module
import electrobot.app as app_module
session=tempfile.TemporaryDirectory()
root_patch=patch.object(app_module,'ROOT',Path(session.name)); root_patch.start()
app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
warnings=[]; QMessageBox.warning=lambda *args:warnings.append(args[-1])
w=Window(); w.show()
def idle():
    deadline=time.monotonic()+5
    while w.busy and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
    app.processEvents(); assert not w.busy
idle()
sdk=FakeSDK()
with tempfile.TemporaryDirectory() as d,patch.object(worker_module,'DobotRobot',side_effect=lambda s,c:DobotRobot(s,c,arm_factory=FakeArm)),patch.object(worker_module,'PalmSensPotentiostat',side_effect=lambda s:PalmSensPotentiostat(s,sdk)),patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
    w.worker.output=Path(d)
    w.mode.setCurrentIndex(1); idle()
    assert not w.device_state['robot'] and not w.device_state['potentiostat']
    w.submit('connect_robot'); idle(); assert w.device_state['robot'] and not w.device_state['homed']
    assert w.experiment_tracker.pose==w.current_pose==w.manual_tracker.pose
    w.submit('home'); idle(); assert w.device_state['homed']
    anchor=dict(w.current_pose)
    moves_before=[c for c in w.worker.robot.arm.calls if isinstance(c,tuple) and c[0]=='move']
    w.preset_button.click(); idle()
    assert [c for c in w.worker.robot.arm.calls if isinstance(c,tuple) and c[0]=='move']==moves_before
    assert w.fields['rack_x'].value()==anchor['x']
    assert w.fields['cell_x'].value()==anchor['x']+10
    assert w.fields['rinse_y'].value()==anchor['y']+10
    assert w.fields['safe_z'].value()==anchor['z']+5
    assert w.current_pose==anchor
    assert not w.fields['calibrated'].isChecked() and not w.fields['fixture_verified'].isChecked()
    assert not w.validation_issues
    w.fields['safe_z'].setValue(anchor['z']); app.processEvents()
    assert 'Travel Z must' in w.calibration_feedback.text() and not w.rehearse.isEnabled()
    w.preset_button.click(); idle(); assert not w.validation_issues
    before=w.read_settings()
    w.apply_compact_rehearsal(dict(anchor,x=295))
    assert w.read_settings()==before
    assert 'Preset not applied' in w.calibration_feedback.text()
    w.update_calibration_feedback()
    w.fields['electrodes'].setValue(1); w.fields['settle'].setValue(0); w.fields['rinse_dwell'].setValue(0); w.fields['grip_dwell'].setValue(.1)
    w.fields['calibrated'].setChecked(True); w.fields['fixture_verified'].setChecked(True)
    w.refresh_controls(); assert w.rehearse.isEnabled() and not w.start.isEnabled()
    w.rehearse.click(); idle(); assert w.state.text()=='Completed'
    assert not w.device_state['potentiostat']
    assert not list(w.output.glob('*.csv'))
    assert json.loads((w.output/'summary.json').read_text())['run_type']=='robot_rehearsal'
    w.submit('connect_potentiostat'); idle(); assert w.device_state['potentiostat']
    w.start_run(); idle(); assert w.state.text()=='Completed'
    summary=json.loads((w.output/'summary.json').read_text()); assert summary['mode']=='hardware'
    assert 'False,nominal_cv_step' in (w.output/'electrode-001.csv').read_text()
    assert not w.pause.isEnabled() and not w.plot.synthetic
    assert sdk.manager.calls[-1]==('cell',False)
    w.fields['calibrated'].setChecked(True); w.fields['rack_x'].setValue(191); assert not w.fields['calibrated'].isChecked()
    w.submit('grip',True); idle(); w.disconnect_devices(); assert not w.busy and w.device_state['robot']
    w.close(); app.processEvents(); assert w.isVisible() and w.worker.isRunning()
    w.submit('grip',False); idle(); w.disconnect_devices(); idle()
    assert not w.device_state['robot'] and not w.device_state['potentiostat']
    assert w.experiment_tracker.pose is None and w.manual_tracker.pose is None
    w.mode.setCurrentIndex(0); idle()
w.close(); deadline=time.monotonic()+3
while w.worker.isRunning() and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
assert not w.worker.isRunning(); assert not warnings,warnings
root_patch.stop(); session.cleanup()
print('Hardware UI: explicit connection/home, real adapter batch, raw-value export, readiness invalidation and held-electrode disconnect/close guards passed (mock devices)')
