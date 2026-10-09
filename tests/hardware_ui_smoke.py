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
    w.submit('connect_potentiostat'); idle(); assert w.device_state['potentiostat']
    w.submit('home'); idle(); assert w.device_state['homed']
    w.fields['electrodes'].setValue(1); w.fields['settle'].setValue(0); w.fields['rinse_dwell'].setValue(0); w.fields['grip_dwell'].setValue(.1)
    w.fields['calibrated'].setChecked(True); w.fields['fixture_verified'].setChecked(True)
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
    w.mode.setCurrentIndex(0); idle()
w.close(); deadline=time.monotonic()+3
while w.worker.isRunning() and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
assert not w.worker.isRunning(); assert not warnings,warnings
print('Hardware UI: explicit connection/home, real adapter batch, raw-value export, readiness invalidation and held-electrode disconnect/close guards passed (mock devices)')
