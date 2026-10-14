"""Lazy hardware adapters. All device calls belong to the device worker thread."""
import asyncio
import math
import time
from pathlib import Path
from .engine import Cancelled
from .robot_checks import segment_samples,response_params,alarm_codes,alarm_description

CURRENT_RANGES={.001:'1nA',.01:'10nA',.1:'100nA',1:'1uA',10:'10uA',100:'100uA',1000:'1mA',10000:'10mA'}

class DobotRobot:
    def __init__(self,s,control,pose_callback=lambda p:None,arm_factory=None):
        self.s=s; self.control=control; self.pose_callback=pose_callback
        self.arm_factory=arm_factory; self.arm=None; self.holding=False; self.homed=False; self.gripper_state='unknown'
        self.diagnostic_callback=lambda d:None
        self.diagnostics={'target':None,'actual':None,'fault':'','alarms':[],'alarm_monitor':'not checked','preflight':'not checked'}
        self._checked=set(); self._check_control=None
    def diagnostic(self,**values):
        self.diagnostics.update(values); self.diagnostic_callback(dict(self.diagnostics))
    def _fault(self,reason):
        target=self.diagnostics['target']; actual=self.diagnostics['actual']
        def fmt(p): return ', '.join(f'{k.upper()}={p[k]:.2f}' for k in ('x','y','z','r')) if p else 'unavailable'
        message=f'{reason}\nRequested: {fmt(target)}\nReported: {fmt(actual)}'
        self.diagnostic(fault=message); return RuntimeError(message)
    def read_alarms(self):
        raw=None
        try:
            raw=self.arm.cmds.get_alarms_state(); codes=alarm_codes(raw)
        except Exception as exc:
            self.diagnostic(alarm_raw=raw,alarm_monitor='unavailable: '+str(exc)); return None
        self.diagnostic(alarms=codes,alarm_raw=raw,alarm_monitor='available')
        return codes
    def check_alarms(self):
        codes=self.read_alarms()
        if codes:
            raise self._fault('Controller alarm: '+', '.join(f'{c} (0x{c:02X}: {alarm_description(c)})' for c in codes)+'. Stop; inspect the robot, clear alarms explicitly, then home before motion.')
    def poll_health(self):
        self.pose()
        try: self.check_alarms()
        except RuntimeError:
            if self.homed: self.stop()
    def clear_alarms(self):
        self.control.check()
        self.stop()
        self.arm.cmds._call('ClearAllAlarmsState',call_timeout=self.s.robot_timeout)
        self.homed=False; self._checked.clear()
        self.check_alarms()
        self.diagnostic(fault=('Alarm clear command sent; feedback unavailable.' if self.diagnostics['alarm_monitor']!='available' else 'Alarms cleared explicitly.')+' Inspect the route and home before motion.')
    def check_pose(self,target,label):
        self.control.check()
        try: self.s.validate_pose(target)
        except ValueError as exc:
            self.diagnostic(rejected_pose=dict(zip(('x','y','z','r'),target)),preflight='Rejected by configured bounds: '+label)
            raise ValueError(str(self._fault('Configured workspace rejected '+label+': '+str(exc)))) from exc
        if not self.s.controller_preflight:
            self.diagnostic(preflight='Controller reachability disabled; configured bounds only'); return
        if self._check_control is not self.control:
            self._checked.clear(); self._check_control=self.control
        key=tuple(round(v,6) for v in target)
        if key in self._checked: return
        try:
            response=response_params(self.arm.cmds._call('CheckPoseLimit',call_timeout=self.s.robot_timeout,
                isJoint=False,**dict(zip(('x','y','z','r'),target))))
            limited=response.get('isLimited') if isinstance(response,dict) else None
            if type(limited) is not bool: raise ValueError('Missing boolean isLimited in controller response')
        except Cancelled: raise
        except Exception as exc:
            self.diagnostic(preflight='Unavailable: '+str(exc))
            raise self._fault('Controller reachability query unavailable: '+str(exc)+'. No movement commanded by this check. If this firmware does not support CheckPoseLimit, the check can be explicitly disabled in Workspace; this reduces protection.') from exc
        if limited:
            self.diagnostic(rejected_pose=dict(zip(('x','y','z','r'),target)),preflight='Rejected: '+label)
            raise self._fault('Controller rejected '+label+f' at sampled XYZ/R {tuple(round(v,2) for v in target)} as outside its pose limits. This check commanded no movement; check travel Z and station coordinates.')
        self._checked.add(key)
    def preflight_route(self,route):
        self._checked.clear(); self._check_control=self.control
        self.pose()
        self.diagnostic(rejected_pose=None)
        self.check_alarms()
        previous=route[0][1]
        for i,(label,target) in enumerate(route):
            self.diagnostic(preflight=f'Checking {i+1}/{len(route)}: {label}',target=dict(zip(('x','y','z','r'),target)))
            for sample in segment_samples(previous,target,self.s.reachability_step): self.check_pose(sample,label)
            previous=target
        self.diagnostic(fault='',preflight=('Controller sampled route passed; not a collision check' if self.s.controller_preflight else 'Configured bounds passed; controller check disabled'))
    def connect(self):
        if self.arm is not None: return
        try:
            if self.arm_factory is None:
                from dobotkit import MagicianLite
                self.arm_factory=MagicianLite
            self.arm=self.arm_factory(port=self.s.robot_port,host=self.s.robot_host,
                ws_port=self.s.robot_ws_port,timeout=self.s.robot_timeout,auto_connect=False)
            self.arm.connect(); self.arm.set_speed(self.s.robot_velocity,self.s.robot_acceleration)
            self.poll_health()
        except Exception:
            if self.arm is not None:
                try: self.arm.disconnect()
                except Exception: pass
            self.arm=None; raise
    def pose(self):
        if self.arm is None: raise RuntimeError('Connect the robot first')
        pose=self.arm.get_pose()
        if not all(math.isfinite(float(pose[k])) for k in ('x','y','z','r')):
            raise RuntimeError('Robot returned an invalid pose')
        self.diagnostic(actual=dict(pose)); self.pose_callback(pose); return pose
    def _wait_index(self,index,timeout,target=None):
        if not isinstance(index,int): raise RuntimeError('Dobot did not return a queued command index')
        deadline=time.monotonic()+timeout; stable=0; last_error='Queue has not completed'
        previous=None; last_progress=time.monotonic(); alarm_read=0
        try:
            while time.monotonic()<deadline:
                self.control.check()
                pose=self.pose()  # Publish measured feedback while the queue is moving.
                now=time.monotonic()
                if now-alarm_read>=.25:
                    self.check_alarms(); alarm_read=now
                if previous is None or math.dist([pose[k] for k in ('x','y','z')],[previous[k] for k in ('x','y','z')])>=.2 or abs((pose['r']-previous['r']+180)%360-180)>=.2:
                    previous=dict(pose); last_progress=now
                if target is not None:
                    xyz_error=math.dist([float(pose[k]) for k in ('x','y','z')],target[:3])
                    rotation_error=abs((float(pose['r'])-target[3]+180)%360-180)
                    if xyz_error<=self.s.position_tolerance and rotation_error<=self.s.rotation_tolerance: last_progress=now
                    elif now-last_progress>=self.s.motion_stall_timeout:
                        raise self._fault(f'No reported motion progress for {self.s.motion_stall_timeout:g} s. Possible reach/joint limit, obstruction or controller fault; cause is not confirmed. Stop and inspect, then home before motion.')
                if self.arm.cmds.current_index()>=index:
                    reached=True
                    if target is not None:
                        xyz_error=math.dist([float(pose[k]) for k in ('x','y','z')],target[:3])
                        rotation_error=abs((float(pose['r'])-target[3]+180)%360-180)
                        reached=xyz_error<=self.s.position_tolerance and rotation_error<=self.s.rotation_tolerance
                        last_error=f'Target error: XYZ {xyz_error:.2f} mm, R {rotation_error:.2f} degrees'
                    stable=stable+1 if reached else 0
                    if stable>=2: return
                else: stable=0
                self.control.wait(.1)
            raise TimeoutError(str(self._fault(f'Motion timeout after {timeout:g} s. {last_error}. Inspect and home before motion.')))
        except Exception as exc:
            if not isinstance(exc,Cancelled) and not self.diagnostics['fault']: self._fault(str(exc))
            try: self.stop()
            except Exception as cleanup: self.diagnostic(fault=self.diagnostics['fault']+'\nRobot stop failed: '+str(cleanup))
            raise
    def home(self):
        self.control.check(); self.check_alarms(); self.arm.cmds.queue_start()
        self.diagnostic(target=dict(zip(('x','y','z','r'),(200.,0.,0.,0.))),rejected_pose=None)
        self._wait_index(self.arm.home(wait=False),self.s.home_timeout,(200.0,0.0,0.0,0.0))
        self.homed=True; self._checked.clear(); self.diagnostic(fault='',preflight='Not checked after homing')
    def move(self,pose):
        if not self.homed: raise RuntimeError('Home the robot in Manual robot before moving')
        target=tuple(pose) if len(pose)==4 else (*pose,self.s.tool_r)
        self.diagnostic(target=dict(zip(('x','y','z','r'),target)),rejected_pose=None)
        self.control.check()
        try: self.s.validate_pose(target)
        except ValueError as exc: raise ValueError(str(self._fault('Configured workspace rejected target: '+str(exc)))) from exc
        self.check_alarms()
        current=self.pose()
        for sample in segment_samples(tuple(current[k] for k in ('x','y','z','r')),target,self.s.reachability_step): self.check_pose(sample,'requested move')
        from dobotkit import PTPMode
        self.arm.set_speed(self.s.robot_velocity,self.s.robot_acceleration)
        index=self.arm.move_to(*target,mode=PTPMode.MOVL_XYZ,wait=False)
        self._wait_index(index,self.s.motion_timeout,target)
    def grip(self,closed):
        self.control.check()
        self.arm.effector.grip(bool(closed),enable=bool(closed),queued=False)
        self.holding=bool(closed)  # Commanded state; not a pickup sensor.
        self.gripper_state='closed' if closed else 'released'
        self.control.wait(self.s.grip_dwell)
    def open_fully(self):
        self.control.check()
        self.arm.effector.grip(False,enable=True,queued=False)
        self.holding=False; self.gripper_state='fully_open'
        self.control.wait(self.s.grip_dwell)
    def stop(self):
        self.homed=False
        if self.arm is not None:
            self.arm.cmds.queue_stop(); self.arm.cmds.queue_clear()
    def disconnect(self):
        if self.arm is None: return
        try: self.stop()
        finally:
            try: self.arm.disconnect()
            finally: self.arm=None

class PalmSensPotentiostat:
    def __init__(self,s,sdk=None):
        self.s=s; self.sdk=sdk; self.manager=None; self.loop=None; self.name='Disconnected'
    def _await(self,coro,timeout=None):
        return self.loop.run_until_complete(asyncio.wait_for(coro,timeout or self.s.sdk_timeout))
    def connect(self):
        if self.manager is not None: return
        try:
            if self.sdk is None:
                try: import pypalmsens as ps
                except Exception as exc:
                    raise RuntimeError('PalmSens SDK could not load. Install requirements-hardware.txt, .NET Desktop Runtime 10+ on Windows, and device drivers. '+str(exc)) from exc
                self.sdk=ps
            self.loop=asyncio.new_event_loop()
            instruments=self._await(self.sdk.discover_async())
            if self.s.potentiostat_id:
                instruments=[i for i in instruments if i.id==self.s.potentiostat_id or i.name==self.s.potentiostat_id]
            if len(instruments)!=1:
                names=', '.join(i.id for i in instruments) or 'none'
                raise RuntimeError(f'Expected one selected potentiostat; found {len(instruments)} ({names}). Set the device ID in Settings.')
            self.manager=self.sdk.InstrumentManagerAsync(instruments[0])
            self._await(self.manager.connect()); self.name=instruments[0].name
            self.cell_off()
        except Exception:
            try: self.disconnect()
            except Exception: pass
            raise
    def method(self,s):
        if not math.isclose(s.end_v,s.start_v,abs_tol=1e-9):
            raise ValueError('PalmSens CV ends at its start potential')
        cr=CURRENT_RANGES[s.current_range_ua]
        return self.sdk.CyclicVoltammetry(begin_potential=s.start_v,
            vertex1_potential=s.vertex1_v,vertex2_potential=s.vertex2_v,
            step_potential=s.step_v,scanrate=s.scan_rate,n_scans=s.cycles,
            equilibration_time=0.0,current_range={'min':cr,'max':cr,'start':cr},
            general={'power_frequency':s.power_frequency})
    def validate_protocol(self,s):
        self.manager.validate_method(self.method(s))
    def cell_off(self):
        if self.manager is not None: self._await(self.manager.set_cell(False))
    def measure(self,s,index,control,point,stream=None):
        method=self.method(s); errors=[]; count=0
        def callback(data):
            nonlocal count
            if errors: return
            try:
                unit=str(data.y_array.unit).replace('μ','u').replace('µ','u').strip()
                factors={'A':1e6,'mA':1e3,'uA':1,'nA':.001,'pA':.000001}
                if unit not in factors: raise ValueError(f'Unsupported PalmSens current unit: {unit}')
                xunit=str(data.x_array.unit).strip()
                if xunit not in ('V','mV'): raise ValueError(f'Unsupported potential unit: {xunit}')
                for row in data.new_datapoints():
                    # CV callback carries E and I; timestamp is nominal sample time.
                    point(count*s.step_v/s.scan_rate,float(row['x'])*(1 if xunit=='V' else .001),float(row['y'])*factors[unit]); count+=1
            except Exception as exc: errors.append(exc)
        async def acquire():
            control.check()
            task=asyncio.create_task(self.manager.measure(method,callback=callback,stream=str(stream) if stream else None))
            deadline=time.monotonic()+s.potential_points()[-1][0]+s.sdk_timeout
            try:
                while not task.done():
                    if control.cancel.is_set(): raise Cancelled()
                    if errors: raise errors[0]
                    if time.monotonic()>deadline: raise TimeoutError('Potentiostat measurement timed out')
                    await asyncio.sleep(.05)
                result=await task
                await asyncio.sleep(0)  # Drain scheduled final-data callbacks.
                if errors: raise errors[0]
                if control.cancel.is_set(): raise Cancelled()
                if count==0: raise RuntimeError('Measurement completed without data')
                return result
            except BaseException:
                try: await asyncio.wait_for(self.manager.abort(),s.sdk_timeout)
                finally:
                    if not task.done(): task.cancel()
                    await asyncio.gather(task,return_exceptions=True)
                raise
            finally:
                await asyncio.wait_for(self.manager.set_cell(False),s.sdk_timeout)
        self.loop.run_until_complete(acquire())
    def disconnect(self):
        try:
            if self.manager is not None:
                try: self.cell_off()
                finally: self._await(self.manager.disconnect())
        finally:
            self.manager=None
            if self.loop is not None: self.loop.close(); self.loop=None
