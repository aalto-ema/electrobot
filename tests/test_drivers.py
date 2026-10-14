import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from electrobot.config import Settings
from electrobot.engine import Control,Cancelled,Experiment,SimRobot,SimPotentiostat
from electrobot.drivers import DobotRobot,PalmSensPotentiostat

class FakeArm:
    def __init__(self,**kwargs):
        self.kwargs=kwargs; self.calls=[]; self.current={'x':200.,'y':0.,'z':0.,'r':0.}
        self.index=0; self.pending=False; self.mismatch=False
        self.alarms=[0]*16; self.limited=lambda p:False; self.unsupported=False
        self.cmds=SimpleNamespace(queue_start=lambda:self.calls.append('start'),
            queue_stop=lambda:self.calls.append('stop'),queue_clear=lambda:self.calls.append('clear'),
            current_index=lambda:0 if self.pending else self.index,
            get_alarms_state=lambda:{'state':self.alarms},_call=self.rpc)
        self.effector=SimpleNamespace(grip=lambda on,enable,queued:self.calls.append(('grip',on,enable,queued)))
    def connect(self): self.calls.append('connect')
    def rpc(self,name,**params):
        self.calls.append(('rpc',name,params))
        if name=='CheckPoseLimit':
            if self.unsupported: raise RuntimeError('Unsupported command')
            return {'isLimited':self.limited(params)}
        if name=='ClearAllAlarmsState': self.alarms=[0]*16; return {}
        raise RuntimeError('Unexpected RPC '+name)
    def disconnect(self): self.calls.append('disconnect')
    def set_speed(self,*args): self.calls.append(('speed',args))
    def get_pose(self): return dict(self.current)
    def home(self,wait):
        self.calls.append(('home',wait)); self.current={'x':200.,'y':0.,'z':0.,'r':0.}; self.index+=1; return self.index
    def move_to(self,*pose,**kwargs):
        self.calls.append(('move',pose,kwargs)); self.index+=1
        if not self.mismatch: self.current=dict(zip(('x','y','z','r'),pose))
        return self.index

class FakeManager:
    def __init__(self,instrument,scenario='normal'):
        self.instrument=instrument; self.scenario=scenario; self.calls=[]
    async def connect(self): self.calls.append('connect')
    async def disconnect(self): self.calls.append('disconnect')
    async def set_cell(self,on): self.calls.append(('cell',on))
    def validate_method(self,method): self.calls.append(('validate',method))
    async def abort(self): self.calls.append('abort')
    async def measure(self,method,callback,stream):
        self.calls.append(('measure',method,stream))
        if self.scenario=='wait':
            await asyncio.sleep(10); return None
        unit='bad' if self.scenario=='bad_unit' else 'mA'
        data=SimpleNamespace(y_array=SimpleNamespace(unit=unit),x_array=SimpleNamespace(unit='V'),
            new_datapoints=lambda:iter([{'x':.1,'y':.002,'index':0},{'x':.2,'y':.003,'index':1}]))
        if self.scenario!='empty': callback(data)
        await asyncio.sleep(.01); return 'measurement'

class FakeSDK:
    def __init__(self,scenario='normal',devices=1):
        self.scenario=scenario; self.devices=devices; self.manager=None
    async def discover_async(self):
        return [SimpleNamespace(id=f'device-{i}',name=f'EmStat4 LR {i}') for i in range(self.devices)]
    def InstrumentManagerAsync(self,instrument):
        self.manager=FakeManager(instrument,self.scenario); return self.manager
    def CyclicVoltammetry(self,*,begin_potential,vertex1_potential,vertex2_potential,
        step_potential,scanrate,n_scans,equilibration_time,current_range,general):
        return dict(begin=begin_potential,v1=vertex1_potential,v2=vertex2_potential,step=step_potential,
            rate=scanrate,cycles=n_scans,settle=equilibration_time,current_range=current_range,general=general)

class DriverTests(unittest.TestCase):
    def robot(self,**kwargs):
        s=Settings(mode='hardware',calibrated=True,fixture_verified=True,grip_dwell=.001,**kwargs)
        robot=DobotRobot(s,Control(),arm_factory=FakeArm); robot.connect(); return robot
    def test_connect_does_not_home_or_move(self):
        r=self.robot(); self.assertFalse(r.homed)
        self.assertFalse(any(isinstance(c,tuple) and c[0] in ('home','move','grip') for c in r.arm.calls))
        with self.assertRaises(RuntimeError): r.move((210,0,20,0))
        r.disconnect()
    def test_homing_motion_pose_and_gripper(self):
        r=self.robot(); r.home(); self.assertTrue(r.homed)
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            r.move((210,0,20,0))
        self.assertEqual(r.pose()['x'],210)
        call=next(c for c in r.arm.calls if isinstance(c,tuple) and c[0]=='move')
        self.assertEqual(call[2],{'mode':2,'wait':False})
        r.grip(True); self.assertTrue(r.holding); self.assertIn(('grip',True,True,False),r.arm.calls)
        r.grip(False); self.assertFalse(r.holding); self.assertEqual(r.gripper_state,'released'); self.assertEqual(r.arm.calls[-1],('grip',False,False,False))
        r.open_fully(); self.assertFalse(r.holding); self.assertEqual(r.gripper_state,'fully_open'); self.assertEqual(r.arm.calls[-1],('grip',False,True,False))
        r.stop(); self.assertFalse(r.homed); self.assertEqual(r.arm.calls[-2:],['stop','clear'])
        r.disconnect()
    def test_outside_workspace_is_not_sent(self):
        r=self.robot(); r.home()
        with self.assertRaises(ValueError): r.move((999,0,0,0))
        self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls))
        r.disconnect()

    def test_controller_rejects_height_before_any_motion(self):
        r=self.robot(safe_z=100); r.home(); r.arm.current['z']=68.8
        r.arm.limited=lambda p:p['z']>70
        start=tuple(r.arm.current[k] for k in ('x','y','z','r'))
        with self.assertRaisesRegex(RuntimeError,'Controller rejected'):
            r.preflight_route(r.s.planned_route(start))
        self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls))
        self.assertEqual(r.diagnostics['target']['z'],100)
        self.assertEqual(r.diagnostics['actual']['z'],68.8)
        self.assertGreater(r.diagnostics['rejected_pose']['z'],70)
        r.disconnect()

    def test_reachability_checks_transfer_interior_and_unsupported_firmware(self):
        r=self.robot(); r.home()
        r.arm.limited=lambda p:205<p['x']<215
        with self.assertRaisesRegex(RuntimeError,'Controller rejected'):
            r.preflight_route([('start',(200,0,20,0)),('transfer',(220,0,20,0))])
        r.arm.limited=lambda p:False; r.arm.unsupported=True
        with self.assertRaisesRegex(RuntimeError,'query unavailable'):
            r.preflight_route([('start',(200,0,20,0))])
        self.assertFalse(any(isinstance(c,tuple) and c[0]=='move' for c in r.arm.calls))
        r.s.controller_preflight=False
        r.preflight_route([('start',(200,0,20,0))])
        self.assertIn('disabled',r.diagnostics['preflight']); r.disconnect()

    def test_alarm_during_motion_stops_queue_and_latches_details(self):
        r=self.robot(); r.home()
        def move(*pose,**kwargs):
            r.arm.calls.append(('move',pose,kwargs)); r.arm.pending=True
            r.arm.alarms[8]=1; r.arm.index+=1; return r.arm.index
        r.arm.move_to=move
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            with self.assertRaisesRegex(RuntimeError,'J1 positive limit'): r.move((210,0,20,0))
        self.assertFalse(r.homed); self.assertEqual(r.diagnostics['alarms'],[64])
        self.assertIn('clear',r.arm.calls); self.assertEqual(r.diagnostics['target']['x'],210)
        r.clear_alarms(); self.assertFalse(r.homed); self.assertEqual(r.diagnostics['alarms'],[])
        r.disconnect()

    def test_silent_stall_reports_target_actual_and_requires_home(self):
        r=self.robot(motion_stall_timeout=.05,motion_timeout=2); r.home(); r.arm.mismatch=True; r.arm.pending=True
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            with self.assertRaisesRegex(RuntimeError,'No reported motion progress'): r.move((210,0,20,0))
        self.assertFalse(r.homed); self.assertIn('Requested:',r.diagnostics['fault']); self.assertIn('Reported:',r.diagnostics['fault'])
        self.assertIn('clear',r.arm.calls); r.disconnect()

    def test_unavailable_alarm_feedback_does_not_disable_stall_watchdog(self):
        r=self.robot(motion_stall_timeout=.05,motion_timeout=2); r.home()
        r.arm.cmds.get_alarms_state=lambda:{'unsupported_format':[]}
        r.arm.mismatch=True; r.arm.pending=True
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}):
            with self.assertRaisesRegex(RuntimeError,'No reported motion progress'): r.move((210,0,20,0))
        self.assertIn('unavailable',r.diagnostics['alarm_monitor']); self.assertFalse(r.homed); r.disconnect()

    def test_batch_preflight_failure_prevents_gripping_and_saves_diagnostics(self):
        r=self.robot(safe_z=100); r.home(); r.arm.limited=lambda p:p['z']>70
        with tempfile.TemporaryDirectory() as folder:
            output,status=Experiment(r.s,r.control,lambda e:None,lambda *p:None,Path(folder),r,None,rehearsal=True).run()
            self.assertEqual(status,'failed')
            self.assertFalse(any(isinstance(c,tuple) and c[0] in ('move','grip') for c in r.arm.calls))
            report=json.loads((output/'robot-diagnostics.json').read_text())
            self.assertIn('Controller rejected',report['fault']); self.assertEqual(report['target']['z'],100)
            self.assertFalse(list(output.glob('*.csv')))
        self.assertFalse(r.homed); r.disconnect()
    def test_motion_mismatch_stops_queue(self):
        r=self.robot(motion_timeout=.15); r.home(); r.arm.mismatch=True
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}),self.assertRaises(TimeoutError):
            r.move((210,0,20,0))
        self.assertIn('stop',r.arm.calls); self.assertFalse(r.homed); r.disconnect()
    def test_stop_during_queued_motion(self):
        r=self.robot(); r.home(); r.arm.pending=True
        timer=threading.Timer(.02,r.control.cancel.set); timer.start()
        try:
            with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}),self.assertRaises(Cancelled):
                r.move((210,0,20,0))
            self.assertIn('clear',r.arm.calls)
        finally: timer.join(); r.disconnect()
    def test_live_pose_published_before_queue_completion(self):
        r=self.robot(); r.home(); r.arm.pending=True
        samples=[]
        def feedback(pose):
            samples.append(dict(pose)); r.control.cancel.set()
        r.pose_callback=feedback
        with patch.dict('sys.modules',{'dobotkit':SimpleNamespace(PTPMode=SimpleNamespace(MOVL_XYZ=2))}),self.assertRaises(Cancelled):
            r.move((210,0,20,0))
        self.assertTrue(samples)
        self.assertTrue(r.arm.pending)
        r.disconnect()
    def test_palm_mapping_units_cell_off_and_stream(self):
        sdk=FakeSDK(); s=Settings(mode='hardware'); p=PalmSensPotentiostat(s,sdk); p.connect()
        samples=[]
        try:
            p.validate_protocol(s); p.measure(s,1,Control(),lambda *args:samples.append(args),stream=Path('raw.jsonl'))
            method=p.method(s)
            self.assertEqual(method['current_range'],{'min':'100uA','max':'100uA','start':'100uA'})
            self.assertEqual(method['cycles'],2); self.assertEqual(method['general'],{'power_frequency':50})
            self.assertEqual([v[1:] for v in samples],[(.1,2),(.2,3)])
            self.assertAlmostEqual(samples[1][0],.05)
            self.assertEqual(sdk.manager.calls[-1],('cell',False))
            self.assertEqual(next(c[2] for c in sdk.manager.calls if isinstance(c,tuple) and c[0]=='measure'),'raw.jsonl')
        finally: p.disconnect()
        self.assertIn('disconnect',sdk.manager.calls)
    def test_palm_abort_on_cancel(self):
        sdk=FakeSDK('wait'); s=Settings(); p=PalmSensPotentiostat(s,sdk); p.connect(); c=Control()
        timer=threading.Timer(.02,c.cancel.set); timer.start()
        try:
            with self.assertRaises(Cancelled): p.measure(s,1,c,lambda *args:None)
            self.assertIn('abort',sdk.manager.calls); self.assertEqual(sdk.manager.calls[-1],('cell',False))
        finally: timer.join(); p.disconnect()
    def test_palm_rejects_unknown_units_and_empty_results(self):
        for scenario in ('bad_unit','empty'):
            with self.subTest(scenario=scenario):
                sdk=FakeSDK(scenario); p=PalmSensPotentiostat(Settings(),sdk); p.connect()
                try:
                    with self.assertRaises((ValueError,RuntimeError)): p.measure(Settings(),1,Control(),lambda *args:None)
                    self.assertIn('abort',sdk.manager.calls)
                finally: p.disconnect()
    def test_palm_ambiguous_selection_and_exact_id(self):
        sdk=FakeSDK(devices=2); p=PalmSensPotentiostat(Settings(),sdk)
        with self.assertRaises(RuntimeError): p.connect()
        self.assertIsNone(p.loop)
        p=PalmSensPotentiostat(Settings(potentiostat_id='device-1'),sdk)
        try: p.connect(); self.assertEqual(sdk.manager.instrument.id,'device-1')
        finally: p.disconnect()
    def test_hardware_preflight_and_no_simulation_fallback(self):
        with self.assertRaises(ValueError): Settings(mode='hardware').validate_batch()
        s=Settings(mode='hardware',calibrated=True,fixture_verified=True)
        with tempfile.TemporaryDirectory() as d,self.assertRaises(RuntimeError):
            Experiment(s,Control(),lambda e:None,lambda *a:None,d).run()
        with self.assertRaises(ValueError): Settings(mode='hardware',end_v=.2).validate()
        with self.assertRaises(ValueError): Settings(mode='hardware',calibrated=True,fixture_verified=True,electrodes=100).validate_batch()
    def test_hardware_sequence_waits_unscaled_and_exports_real_flag(self):
        class ImmediateControl(Control):
            def __init__(self): super().__init__(); self.durations=[]
            def wait(self,t): self.durations.append(t); self.check()
        with tempfile.TemporaryDirectory() as d:
            s=Settings(mode='hardware',calibrated=True,fixture_verified=True,electrodes=1,simulation_speed=100)
            c=ImmediateControl(); r=SimRobot(s,c); p=SimPotentiostat(s)
            folder,status=Experiment(s,c,lambda e:None,lambda *a:None,d,r,p).run()
            self.assertEqual(status,'completed'); self.assertIn(s.settle,c.durations); self.assertIn(s.rinse_dwell,c.durations)
            summary=json.loads((folder/'summary.json').read_text()); self.assertEqual(summary['mode'],'hardware')
            self.assertIn('False,nominal_cv_step',(folder/'electrode-001.csv').read_text())
    def test_measurement_failure_does_not_retrieve_and_keeps_logs(self):
        class FailingPot(SimPotentiostat):
            def measure(self,*args,**kwargs): raise RuntimeError('USB disconnected')
        with tempfile.TemporaryDirectory() as d:
            events=[]; s=Settings(simulation_speed=10000,electrodes=1)
            folder,status=Experiment(s,Control(),events.append,lambda *a:None,d,potentiostat=FailingPot()).run()
            self.assertEqual(status,'failed'); self.assertNotIn('retrieve',[e['state'] for e in events])
            self.assertIn('USB disconnected',(folder/'events.json').read_text())

if __name__=='__main__': unittest.main()
