import json
import math
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch
from electrobot.config import Settings
from electrobot.drivers import DobotRobot
from electrobot.engine import Control
from test_drivers import FakeArm


class OptionalWorkspaceTests(unittest.TestCase):
    def test_default_and_old_profiles_do_not_enforce_bounds(self):
        s=Settings()
        old=asdict(s); old.pop('workspace_enabled')
        self.assertFalse(Settings(**old).workspace_enabled)
        for pose in ((110,0,-60,0),(320,0,160,0)):
            self.assertEqual(s.validate_pose(pose),pose)
        s.cell_x=320; s.safe_z=160
        self.assertEqual(s.calibration_issues(),[])
        s.validate_batch()
        s.workspace_enabled=True
        self.assertTrue(s.calibration_issues())
        with self.assertRaises(ValueError): s.validate_pose((320,0,160,0))
        self.assertTrue(Settings(**json.loads(json.dumps(asdict(s)))).workspace_enabled)

    def test_disabled_bounds_keep_input_and_route_validation(self):
        s=Settings(workspace_x_min=400,workspace_x_max=-400)
        s.validate()
        for pose in ((float('nan'),0,0),(200,0,0,91)):
            with self.assertRaises(ValueError): s.validate_pose(pose)
        s.safe_z=s.cell_z
        self.assertTrue(any('Travel Z must' in m for _,m in s.calibration_issues()))

    def test_controller_still_rejects_with_application_limits_off(self):
        s=Settings(mode='hardware',workspace_radius_max=150)
        r=DobotRobot(s,Control(),arm_factory=FakeArm); r.connect(); r.home()
        try:
            with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
                r.move((320,0,0,0))
            self.assertEqual(r.pose()['x'],320)
            self.assertTrue(any(isinstance(c,tuple) and c[:2]==('rpc','CheckPoseLimit') for c in r.arm.calls))
            r.arm.limited=lambda p:p['x']>325
            moves=sum(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls)
            with self.assertRaisesRegex(RuntimeError,'Controller rejected'): r.move((330,0,0,0))
            self.assertEqual(sum(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls),moves)
        finally: r.disconnect()

    def test_32_slot_preset_preserves_devices_and_protocol(self):
        original=Settings(robot_port='COM8',scan_rate=.2,workspace_enabled=True,calibrated=True,fixture_verified=True)
        s=original.screening_preset().validate()
        self.assertEqual(s.calibration_issues(),[])
        self.assertEqual(len(s.rack_export_positions()),32)
        self.assertEqual((s.electrodes,s.rack_columns,s.robot_port,s.scan_rate),(32,16,'COM8',.2))
        self.assertFalse(s.workspace_enabled or s.calibrated or s.fixture_verified)
        points=s.rack_export_positions()
        self.assertAlmostEqual(math.hypot(*points[0][:2]),210)
        self.assertAlmostEqual(math.hypot(*points[16][:2]),250)
        self.assertGreater(min(math.dist(a[:2],b[:2]) for i,a in enumerate(points) for b in points[i+1:]),34)
        for x,y in ((s.cell_x,s.cell_y),(s.rinse_x,s.rinse_y)):
            self.assertGreater(min(math.dist((x,y),p[:2]) for p in points),50)
        self.assertEqual(s.screening_preset(),s)
