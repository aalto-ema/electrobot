import unittest
from electrobot.robot_checks import alarm_codes,alarm_description,segment_samples
from electrobot.config import Settings


class RobotCheckTests(unittest.TestCase):
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
