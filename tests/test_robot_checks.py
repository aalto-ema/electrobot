import unittest
from electrobot.robot_checks import alarm_codes,alarm_description,segment_samples
from electrobot.config import Settings


class RobotCheckTests(unittest.TestCase):
    def test_workspace_numerical_allowance_is_small_and_absolute(self):
        s=Settings(workspace_x_min=120,workspace_x_max=300,
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
        s=Settings(workspace_z_min=0,rack_z=-3.57628e-06,
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
        s=Settings(safe_z=100)
        route=s.planned_route((200,0,68.8,0))
        self.assertEqual(route[1][1],(200,0,100,0))
        samples=segment_samples((200,0,0,0),(-200,0,0,0),37)
        self.assertTrue(any(abs(p[0])<1e-10 for p in samples))
        with self.assertRaises(ValueError):
            for p in samples: s.validate_pose(p)
