import json
import math
import unittest
from dataclasses import asdict,replace
from types import SimpleNamespace
from unittest.mock import patch
from electrobot.config import Settings
from electrobot.layout_planner import LayoutPlanner,simplify_transfers,validate_plan
from electrobot.robot_checks import segment_samples
from electrobot.drivers import DobotRobot
from electrobot.engine import Control,Cancelled
from test_drivers import FakeArm


class ImmediateControl(Control):
    def wait(self,seconds): self.check()


class QueuedArm(FakeArm):
    def __init__(self,**kwargs):
        super().__init__(**kwargs); self.current['z']=80.; self.running=True
        self.queue=[]; self.completed=0; self.capacity=3; self.peak=0
        self.after_enqueue=lambda:None; self.after_execute=lambda:None
        self.cmds.queue_stop=self.queue_stop; self.cmds.queue_start=self.queue_start
        self.cmds.queue_clear=self.queue_clear; self.cmds.current_index=lambda:self.completed
    def queue_stop(self): self.calls.append('stop'); self.running=False
    def queue_start(self): self.calls.append('start'); self.running=True
    def queue_clear(self): self.calls.append('clear'); self.queue=[]
    def rpc(self,name,**params):
        if name=='GetQueuedCmdLeftSpace':
            self.calls.append(('rpc',name,params))
            if self.unsupported: raise RuntimeError('Unsupported command')
            return {'leftSpace':float(self.capacity-len(self.queue))}
        return super().rpc(name,**params)
    def move_to(self,*pose,**kwargs):
        self.calls.append(('move',pose,kwargs)); self.index+=1
        assert len(self.queue)<self.capacity
        self.queue.append((self.index,pose)); self.peak=max(self.peak,len(self.queue))
        self.after_enqueue(); return self.index
    def get_pose(self):
        if self.running and self.queue:
            index,pose=self.queue.pop(0); self.completed=index
            if not self.mismatch: self.current=dict(zip(('x','y','z','r'),pose))
            self.calls.append(('executed',index)); self.after_execute()
        return dict(self.current)


class MotionOptionsTests(unittest.TestCase):
    def test_simplification_preserves_rejected_chord_and_reduces_waypoints(self):
        s=replace(Settings().screening_preset(),cell_x=0.,cell_y=-220.,rinse_x=0.,rinse_y=220.,rinse_dips=1)
        limited=lambda p:math.hypot(*p[:2])<190 or math.hypot(*p[:2])>310
        s=LayoutPlanner(s,limited).find((220,0,0,0),4)
        initial=(220,0,0,0); before=s.planned_route(initial)
        checker=LayoutPlanner(s,limited)
        s.transfer_plan=simplify_transfers(s,initial,checker.segment)
        self.assertTrue(s.transfer_plan['shortcut_edges'])
        self.assertEqual(s.planned_route(initial),before) # Checkbox off uses original graph.
        s.route_simplification=True
        after=s.planned_route(initial); self.assertLess(len(after),len(before))
        for (_,a),(_,b) in zip(after,after[1:]):
            self.assertFalse(any(limited(p) for p in segment_samples(a,b,s.reachability_step)))
        self.assertEqual(Settings(**json.loads(json.dumps(asdict(s)))).planned_route(initial),after)
        s.transfer_plan['shortcut_edges'].append([0,999999])
        with self.assertRaises(ValueError): validate_plan(s.transfer_plan)

    def test_planner_simplification_checkbox_is_used_in_saved_preview(self):
        s=replace(Settings().screening_preset(),route_simplification=True)
        result=LayoutPlanner(s,lambda p:False).find((200,0,0,0),3)
        self.assertTrue(result.transfer_plan['shortcut_edges'])
        self.assertLess(len(result.planned_route((200,0,0,0))),len(replace(result,route_simplification=False).planned_route((200,0,0,0))))

    def robot(self,**kwargs):
        s=Settings(continuous_motion=True,**kwargs)
        r=DobotRobot(s,ImmediateControl(),arm_factory=QueuedArm); r.connect(); r.homed=True
        return r
    def transfer(self,r,points):
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            r.transfer(points)

    def test_repeated_lift_does_not_enqueue_stationary_motion(self):
        robot=self.robot()
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            robot.move((201,0,80,0))
            robot.move((201,0,80,0))
            robot.s.robot_velocity+=1
            robot.move((202,0,80,0))
        calls=robot.arm.calls
        self.assertEqual([c[1][0] for c in calls if c[0]=='move'],[201,202])
        self.assertEqual(sum(c[0]=='speed' for c in calls),2)

    def test_streams_bounded_queue_with_no_per_waypoint_wait_and_final_verification(self):
        r=self.robot(); points=[(200+i,0,80,0) for i in range(1,24)]
        self.transfer(r,points)
        self.assertEqual(r.pose()['x'],223); self.assertTrue(r.homed)
        self.assertEqual(r.arm.peak,3)
        calls=r.arm.calls; first_start=calls.index('start')
        self.assertEqual(sum(isinstance(c,tuple) and c[0]=='move' for c in calls[:first_start]),3)
        self.assertEqual(sum(c=='start' for c in calls),1)
        self.assertEqual(sum(isinstance(c,tuple) and c[0]=='executed' for c in calls),23)
        self.assertEqual(r.arm.queue,[])
        r.disconnect()

    def test_rejected_segment_and_unsupported_queue_do_not_upload_moves(self):
        for unsupported in (False,True):
            r=self.robot(); r.arm.unsupported=unsupported
            if not unsupported: r.arm.limited=lambda p:p['x']>205
            with self.assertRaises(RuntimeError): self.transfer(r,[(210,0,80,0)])
            self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls))
            r.disconnect()

    def test_upload_failure_or_cancellation_clears_buffer_before_start(self):
        for cancel in (False,True):
            r=self.robot()
            if cancel: r.arm.after_enqueue=r.control.cancel.set
            else:
                original=r.arm.move_to
                def bad(*p,**kw): original(*p,**kw); return None
                r.arm.move_to=bad
            with self.assertRaises((Cancelled,RuntimeError)): self.transfer(r,[(210,0,80,0),(220,0,80,0)])
            self.assertFalse(r.homed); self.assertEqual(r.arm.queue,[])
            self.assertNotIn('start',r.arm.calls)
            self.assertFalse(any(isinstance(c,tuple) and c[0]=='executed' for c in r.arm.calls))
            r.disconnect()

    def test_cancel_alarm_and_final_pose_mismatch_stop_and_clear(self):
        for failure in ('cancel','alarm','mismatch'):
            r=self.robot(motion_timeout=.005,motion_stall_timeout=.001)
            if failure=='cancel': r.arm.after_execute=r.control.cancel.set
            if failure=='alarm': r.arm.after_execute=lambda:setattr(r.arm,'alarms',[1])
            if failure=='mismatch': r.arm.mismatch=True
            with self.assertRaises((Cancelled,RuntimeError,TimeoutError)):
                self.transfer(r,[(210,0,80,0),(220,0,80,0),(230,0,80,0),(240,0,80,0)])
            self.assertFalse(r.homed); self.assertEqual(r.arm.queue,[])
            r.disconnect()

    def test_continuous_rejects_vertical_or_rotation_changes(self):
        for point in ((210,0,70,0),(210,0,80,5)):
            r=self.robot()
            with self.assertRaises(ValueError): self.transfer(r,[point])
            self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls))
            r.disconnect()

    def test_settings_are_opt_in_and_simplification_requires_controller_checks(self):
        self.assertFalse(Settings().route_simplification or Settings().continuous_motion)
        s=Settings(route_simplification=True,continuous_motion=True)
        restored=Settings(**json.loads(json.dumps(asdict(s)))).validate()
        self.assertTrue(restored.route_simplification and restored.continuous_motion)
        with self.assertRaises(ValueError): replace(s,controller_preflight=False).validate()
