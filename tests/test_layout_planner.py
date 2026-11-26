import json
import math
import tempfile
import unittest
from dataclasses import asdict,replace
from electrobot.config import Settings
from electrobot.layout_planner import LayoutPlanner,transfer_waypoints,validate_plan
from electrobot.robot_checks import segment_samples
from electrobot.engine import Control,Cancelled,Experiment,SimRobot


class PlannerTests(unittest.TestCase):
    def settings(self):
        return replace(Settings().screening_preset(),cell_x=0,cell_y=-220,rinse_x=0,rinse_y=220,
                       rinse_dips=1,settle=0,rinse_dwell=0,grip_dwell=.001)
    @staticmethod
    def limited(p): return math.hypot(*p[:2])<190 or math.hypot(*p[:2])>310
    def plan(self,**kwargs):
        return LayoutPlanner(self.settings(),self.limited).find((220,0,0,0),**kwargs)

    def test_routes_around_rejected_chord_and_checks_every_segment(self):
        s=self.plan()
        cell=(s.cell_x,s.cell_y,s.cell_z,0); rinse=(s.rinse_x,s.rinse_y,s.rinse_z,0)
        self.assertTrue(any(self.limited(p) for p in segment_samples((0,-220,40,0),(0,220,40,0),10)))
        route=s.planned_route((220,0,0,0))
        for (_,a),(_,b) in zip(route,route[1:]):
            self.assertFalse(any(self.limited(p) for p in segment_samples(a,b,s.reachability_step)))
        self.assertGreater(len(transfer_waypoints(s,cell,rinse)),3)
        self.assertEqual(s.electrodes,32)
        self.assertEqual((s.rack_z,s.cell_z,s.rinse_z,s.safe_z),(0,0,0,40))
        self.assertEqual(Settings(**json.loads(json.dumps(asdict(s)))).transfer_plan,s.transfer_plan)

    def test_capacity_is_best_in_sampled_search_and_not_silent_reduction(self):
        s=replace(self.settings(),cell_x=230,cell_y=-30,rinse_x=230,rinse_y=30)
        limited=lambda p:not (210<=math.hypot(*p[:2])<=290 and abs(math.degrees(math.atan2(p[1],p[0])))<=25)
        result=LayoutPlanner(s,limited).find((220,0,0,0),100,36)
        self.assertGreater(result.electrodes,0); self.assertLess(result.electrodes,100)
        self.assertEqual(result.electrodes,result.transfer_plan['capacity'])
        self.assertEqual(result.transfer_plan['requested'],100)
        self.assertFalse(result.calibrated or result.fixture_verified)

    def test_vertical_interior_rejection_identifies_taught_station(self):
        with self.assertRaisesRegex(ValueError,'Cell seating/lift is rejected'):
            LayoutPlanner(self.settings(),lambda p:10<=p[2]<=30).find((220,0,0,0))

    def test_cancel_unsupported_and_query_budget_do_not_propose_layout(self):
        def cancelled(): raise Cancelled()
        with self.assertRaises(Cancelled): LayoutPlanner(self.settings(),self.limited,check=cancelled).find((220,0,0,0))
        def unsupported(p): raise RuntimeError('Unsupported command')
        with self.assertRaisesRegex(RuntimeError,'Unsupported'): LayoutPlanner(self.settings(),unsupported).find((220,0,0,0))
        with self.assertRaisesRegex(ValueError,'budget'): LayoutPlanner(self.settings(),self.limited,max_queries=1).find((220,0,0,0))
        with self.assertRaisesRegex(ValueError,'boolean'): LayoutPlanner(self.settings(),lambda p:None).find((220,0,0,0))

    def test_stale_plan_and_new_initial_location_do_not_fall_back_to_chord(self):
        s=self.plan(count=3)
        s.safe_z+=1
        self.assertTrue(any('out of date' in m for _,m in s.calibration_issues()))
        with self.assertRaisesRegex(ValueError,'changed'): s.planned_route((220,0,0,0))
        s.safe_z-=1
        with self.assertRaisesRegex(ValueError,'outside the saved'): s.planned_route((-250,0,0,0))
        s.transfer_plan['edges'].append([0,99999])
        with self.assertRaisesRegex(ValueError,'edge'): validate_plan(s.transfer_plan)

    def test_rehearsal_executes_exact_preflight_waypoints(self):
        s=self.plan(count=3); s.mode='hardware'; s.calibrated=True; s.fixture_verified=True; s.continuous_motion=True
        class ImmediateControl(Control):
            def wait(self,seconds): self.check()
        class RecordingRobot(SimRobot):
            def __init__(self,s,c):
                super().__init__(s,c); self.current_pose=dict(x=220,y=0,z=0,r=0); self.moves=[]; self.transfers=[]
            def move(self,p):
                self.moves.append(tuple(p) if len(p)==4 else (*p,self.s.tool_r))
                self.current_pose=dict(zip(('x','y','z','r'),self.moves[-1]))
            def transfer(self,points):
                self.transfers.append(list(points))
                self.assert_horizontal=all(p[2]==self.s.safe_z and p[3]==self.s.tool_r for p in points)
                assert self.assert_horizontal
                super().transfer(points)
            def preflight_route(self,route): self.checked=route
        c=ImmediateControl(); robot=RecordingRobot(s,c)
        with tempfile.TemporaryDirectory() as d:
            _,status=Experiment(s,c,lambda e:None,lambda *a:self.fail('Rehearsal measured'),d,robot=robot,rehearsal=True).run()
        self.assertEqual(status,'completed')
        self.assertTrue(robot.transfers)
        self.assertEqual(robot.moves,[p for _,p in robot.checked[1:]])

    def test_subset_rehearsal_and_protocol_changes_reuse_plan(self):
        s=self.plan()
        subset=replace(s,first_electrode=2,electrodes=3,rinse_dips=2,rinse_dwell=2,scan_rate=.2)
        self.assertFalse(subset.calibration_issues())
        self.assertTrue(subset.planned_route((220,0,0,0)))
        beyond=replace(s,electrodes=s.transfer_plan['slot_count']+1)
        self.assertTrue(any('beyond' in m for _,m in beyond.calibration_issues()))
        with self.assertRaisesRegex(ValueError,'beyond'): beyond.planned_route((220,0,0,0))

    def test_optional_application_bounds_are_respected_when_enabled(self):
        s=replace(self.settings(),workspace_enabled=True,workspace_radius_min=250)
        with self.assertRaisesRegex(ValueError,'Cell seating/lift'):
            LayoutPlanner(s,lambda p:False).find((260,0,0,0))
