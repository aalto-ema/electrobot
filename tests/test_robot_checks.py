import unittest
from electrobot.robot_checks import alarm_codes,alarm_description,segment_samples
from electrobot.config import Settings


class RobotCheckTests(unittest.TestCase):
    def test_workspace_numerical_allowance_is_small_and_absolute(self):
        s=Settings(workspace_enabled=True,workspace_x_min=120,workspace_x_max=300,
                   workspace_y_min=0,workspace_y_max=100,workspace_z_min=0,workspace_z_max=50)
        for pose in ((200,0,-3.57628e-06),(120-3e-6,0,0),(300+3e-6,0,0),
                     (200,-3e-6,0),(200,100+3e-6,0),(200,0,50+3e-6)):
            with self.subTest(pose=pose): self.assertEqual(s.validate_pose(pose),pose)
        for pose in ((200,0,-.001),(119.999,0,0),(300.001,0,0),
                     (200,-.001,0),(200,100.001,0),(200,0,50.001),(200,0,float('nan'))):
            with self.subTest(pose=pose), self.assertRaises(ValueError): s.validate_pose(pose)
        s.workspace_x_min=-300; s.workspace_x_max=400
        for radius in (120-3e-6,300+3e-6): s.validate_pose((radius,0,0))
        for radius in (119.999,300.001):
            with self.assertRaisesRegex(ValueError,'radius'): s.validate_pose((radius,0,0))

    def test_calibration_uses_same_workspace_allowance(self):
        s=Settings(workspace_enabled=True,workspace_z_min=0,rack_z=-3.57628e-06,
                   workspace_z_max=80-3e-6,safe_z=80)
        self.assertFalse(any('outside workspace' in message for _,message in s.calibration_issues()))
        s.rack_z=-.001; s.safe_z=80.001
        messages=[message for _,message in s.calibration_issues()]
        self.assertTrue(any('Rack slot 1 Z=' in message for message in messages))
        self.assertIn('Travel Z is outside workspace Z limits.',messages)

    def test_bitmask_alarm_response_and_invalid_data(self):
        bits=[0]*16; bits[2]=4; bits[8]=3
        self.assertEqual(alarm_codes({'result':{'params':{'state':bits}}}),[18,64,65])
        self.assertEqual(alarm_codes({'state':[]}),[])
        self.assertEqual(alarm_description(18),'planning joint limit')
        for raw in ({'unknown':[]},{'state':[256]},{'state':[True]},None):
            with self.assertRaises(ValueError): alarm_codes(raw)

    def test_route_contains_travel_z_and_segment_inner_exclusion(self):
        s=Settings(workspace_enabled=True,safe_z=100)
        route=s.planned_route((200,0,68.8,0))
        self.assertEqual(route[1][1],(200,0,100,0))
        samples=segment_samples((200,0,0,0),(-200,0,0,0),37)
        self.assertTrue(any(abs(p[0])<1e-10 for p in samples))
        with self.assertRaises(ValueError):
            for p in samples: s.validate_pose(p)


class PreflightAlarmTests(unittest.TestCase):
    def test_alarm_raised_by_query_prevents_pass_without_movement(self):
        from electrobot.drivers import DobotRobot
        from electrobot.engine import Control
        from test_drivers import FakeArm
        robot=DobotRobot(Settings(),Control(),arm_factory=FakeArm)
        robot.connect()
        def query(p):
            robot.arm.alarms[12]=16  # alarm 100
            return False
        robot.arm.limited=query
        with self.assertRaisesRegex(RuntimeError,'100.*'):
            robot.preflight_route([('initial',(200,0,0,0)),('lift',(200,0,80,0))])
        self.assertNotIn('passed',robot.diagnostics['preflight'])
        self.assertEqual(robot.diagnostics['last_query_pose']['z'],0)
        self.assertIn('route validation:',robot.diagnostics['fault'])
        self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in robot.arm.calls))

    def test_shortcut_alarm_does_not_publish_plan(self):
        from unittest.mock import patch
        from electrobot.drivers import DobotRobot
        from electrobot.engine import Control
        from test_drivers import FakeArm
        from electrobot.layout_planner import FORMAT,signature
        s=Settings(route_simplification=True)
        original=dict(format=FORMAT,signature=signature(s),slot_count=3,
            initial_pose=[200,0,0,0],nodes=[[200,0,80,0],[210,0,80,0]],edges=[[0,1]])
        s.transfer_plan=original
        robot=DobotRobot(s,Control(),arm_factory=FakeArm); robot.connect()
        def simplify(*args):
            robot.arm.alarms[12]=16
            return {'replacement':True}
        with patch('electrobot.layout_planner.simplify_transfers',side_effect=simplify):
            with self.assertRaisesRegex(RuntimeError,'after shortcut queries'):
                robot.prepare_transfers((200,0,0,0))
        self.assertEqual(s.transfer_plan,original)

    def test_mac_auto_ignores_system_ports_and_requires_unique_available_usb(self):
        from electrobot.drivers import mac_robot_port
        ports=[{'portName':p,'status':'unconnected'} for p in
               ('cu.Bluetooth-Incoming-Port','cu.debug-console','tty.usbmodem1','cu.usbmodem1')]
        self.assertEqual(mac_robot_port(ports),'cu.usbmodem1')
        with self.assertRaisesRegex(RuntimeError,'Select'):
            mac_robot_port(ports+[{'portName':'cu.usbserial2','status':'unconnected'}])
        ports[-1]['status']='connected'
        with self.assertRaisesRegex(RuntimeError,'unavailable'): mac_robot_port(ports)

    def test_direct_speed_applies_cartesian_and_full_ratio(self):
        from types import SimpleNamespace
        from electrobot.drivers import DobotRobot
        from electrobot.engine import Control
        calls=[]
        robot=DobotRobot(Settings(robot_direct_speed=True),Control())
        robot.arm=SimpleNamespace(cmds=SimpleNamespace(
            set_ptp_coordinate_params=lambda *v:calls.append(('cartesian',v)),
            set_ptp_common_params=lambda *v:calls.append(('ratio',v))),
            set_speed=lambda *v:calls.append(('legacy',v)))
        robot._apply_speed(); robot._apply_speed()
        self.assertEqual(calls,[('cartesian',(20,20)),('ratio',(100,100))])
        robot.s.robot_direct_speed=False
        robot._apply_speed()
        self.assertEqual(calls[-1],('legacy',(20,20)))

    def test_saved_shortcuts_are_reused_but_stale_geometry_is_rejected(self):
        from unittest.mock import patch
        from electrobot.drivers import DobotRobot
        from electrobot.engine import Control
        from electrobot.layout_planner import FORMAT,signature
        from test_drivers import FakeArm
        s=Settings(route_simplification=True)
        s.transfer_plan=dict(format=FORMAT,signature=signature(s),slot_count=3,
            initial_pose=[200,0,0,0],nodes=[[200,0,80,0],[210,0,80,0]],
            edges=[[0,1]],shortcut_edges=[[0,1]])
        robot=DobotRobot(s,Control(),arm_factory=FakeArm);robot.connect()
        with patch('electrobot.layout_planner.simplify_transfers') as compiler:
            robot.prepare_transfers((200,0,0,0))
            compiler.assert_not_called()
        s.safe_z+=1
        with self.assertRaisesRegex(ValueError,'settings changed'):
            robot.prepare_transfers((200,0,0,0))

    def test_reachability_query_is_paced_and_cancellable(self):
        from unittest.mock import patch,Mock
        from electrobot.drivers import DobotRobot
        from electrobot.engine import Control,Cancelled
        from test_drivers import FakeArm
        control=Control()
        robot=DobotRobot(Settings(),control,arm_factory=FakeArm);robot.connect()
        control.wait=Mock()
        with patch('electrobot.drivers.time.monotonic',return_value=10):
            robot.controller_limited((200,0,0,0))
            robot.controller_limited((201,0,0,0))
        self.assertAlmostEqual(control.wait.call_args.args[0],robot.LIMIT_QUERY_INTERVAL)
        control.cancel.set()
        before=len(robot.arm.calls)
        with self.assertRaises(Cancelled): robot.controller_limited((202,0,0,0))
        self.assertEqual(len(robot.arm.calls),before)
