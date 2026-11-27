"""Controller-guided setup UI with a mock arm; no physical device access."""
import json,math,sys,tempfile,time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication,QMessageBox
import electrobot.app as app_module
import electrobot.worker as worker_module
from electrobot.app import Window,STYLE
from electrobot.config import Settings
from electrobot.drivers import DobotRobot
from test_drivers import FakeArm

app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
warnings=[]
with patch.object(DobotRobot,'LIMIT_QUERY_INTERVAL',0),tempfile.TemporaryDirectory() as directory,patch.object(app_module,'ROOT',Path(directory)),patch.object(QMessageBox,'warning',side_effect=lambda *a:warnings.append(a[-1])),patch.object(worker_module,'DobotRobot',side_effect=lambda s,c:DobotRobot(s,c,arm_factory=FakeArm)):
    w=Window(); w.show()
    def idle():
        deadline=time.monotonic()+30
        while w.busy and time.monotonic()<deadline: app.processEvents(); time.sleep(.005)
        app.processEvents(); assert not w.busy
    try:
        idle(); w.open_layout_wizard(); wizard=w.layout_wizard
        assert not wizard.find.isEnabled()
        wizard.close(); w.mode.setCurrentIndex(1); idle(); w.submit('connect_robot'); idle(); w.submit('home'); idle()
        arm=w.worker.robot.arm
        arm.current=dict(x=220.,y=0.,z=0.,r=0.)
        s=replace(w.read_settings().screening_preset(),cell_x=0.,cell_y=-220.,rinse_x=0.,rinse_y=220.)
        w.apply_settings(s)
        # Recreate before teaching to reflect the deliberately changed starting profile.
        wizard.deleteLater(); w.layout_wizard=None; w.open_layout_wizard(); wizard=w.layout_wizard
        calls=len(arm.calls)
        wizard.capture_requested.emit('rack'); idle()
        assert wizard.fields['rack_z'].value()==0 and not wizard.confirm.isChecked()
        wizard.confirm.setChecked(True)
        assert wizard.find.isEnabled()
        wizard.grab().save('cad/ui-layout-teaching.png')
        arm.limited=lambda p:math.hypot(p['x'],p['y'])<190 or math.hypot(p['x'],p['y'])>310
        before=w.read_settings()
        wizard.find.click(); idle()
        assert not warnings,warnings
        assert wizard.proposal and wizard.proposal.electrodes==32
        assert w.read_settings()==before  # Preview never applies automatically.
        assert w.device_state['homed']
        assert not any(c=='clear' or isinstance(c,tuple) and c[0] in ('move','home','grip') for c in arm.calls[calls:])
        wizard.grab().save('cad/ui-layout-preview.png')
        wizard.resize(850,680); app.processEvents(); wizard.grab().save('cad/ui-layout-preview-compact.png')
        assert wizard.width()<=850 and wizard.height()<=680
        assert not wizard.apply.isEnabled()
        wizard.review.setChecked(True); wizard.apply.click(); app.processEvents()
        applied=w.read_settings(); assert applied.transfer_plan and applied.electrodes==32
        original_waypoints=len(applied.planned_route((220,0,0,0)))
        w.fields['route_simplification'].setChecked(True)
        calls=len(arm.calls); w.submit('check_route'); idle()
        applied=w.read_settings()
        assert applied.transfer_plan['shortcut_edges']
        assert len(applied.planned_route((220,0,0,0)))<original_waypoints
        assert 'passed' in w.robot_diagnostics['preflight']
        assert not any(c=='clear' or isinstance(c,tuple) and c[0] in ('move','home','grip') for c in arm.calls[calls:])

        assert not applied.calibrated and not applied.fixture_verified
        assert 'applied' in wizard.status.text()
        w.save(); assert json.loads(Path(directory,'settings.json').read_text())['transfer_plan']==applied.transfer_plan
        # Parameter edits do not silently execute an obsolete route.
        w.fields['safe_z'].setValue(41)
        assert any('out of date' in m for _,m in w.validation_issues)
        w.fields['safe_z'].setValue(40)
        # Explicit cancellation of a read-only search must preserve homing.
        wizard.confirm.setChecked(True)
        def cancel_query(p): w.worker.cancel(); return False
        arm.limited=cancel_query; calls=len(arm.calls)
        wizard.find.click(); idle()
        assert wizard.proposal is None and w.device_state['homed']
        assert not any(c=='clear' for c in arm.calls[calls:])
        assert w.read_settings().transfer_plan==applied.transfer_plan
        # Unsupported firmware offers no partial/fallback proposal.
        arm.limited=lambda p:False; arm.unsupported=True
        wizard.find.click(); idle()
        assert wizard.proposal is None and 'Unsupported' in wizard.status.text()
        assert warnings; warnings.clear(); arm.unsupported=False
        w.clear_transfer_plan(); assert not w.read_settings().transfer_plan
        wizard.close()
    finally:
        w.close(); deadline=time.monotonic()+5
        while w.worker.isRunning() and time.monotonic()<deadline: app.processEvents(); time.sleep(.01)
        assert not w.worker.isRunning()
print('Layout UI: teaching, controller-only search, preview/apply, saved routes, stale settings, cancellation and unsupported firmware passed')
