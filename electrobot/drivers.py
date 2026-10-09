"""Lazy hardware adapters. All device calls belong to the device worker thread."""
import asyncio
import math
import time
from pathlib import Path
from .engine import Cancelled

CURRENT_RANGES={.001:'1nA',.01:'10nA',.1:'100nA',1:'1uA',10:'10uA',100:'100uA',1000:'1mA',10000:'10mA'}

class DobotRobot:
    def __init__(self,s,control,pose_callback=lambda p:None,arm_factory=None):
        self.s=s; self.control=control; self.pose_callback=pose_callback
        self.arm_factory=arm_factory; self.arm=None; self.holding=False; self.homed=False
    def connect(self):
        if self.arm is not None: return
        try:
            if self.arm_factory is None:
                from dobotkit import MagicianLite
                self.arm_factory=MagicianLite
            self.arm=self.arm_factory(port=self.s.robot_port,host=self.s.robot_host,
                ws_port=self.s.robot_ws_port,timeout=self.s.robot_timeout,auto_connect=False)
            self.arm.connect(); self.arm.set_speed(self.s.robot_velocity,self.s.robot_acceleration)
            self.pose()
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
        self.pose_callback(pose); return pose
    def _wait_index(self,index,timeout,target=None):
        if not isinstance(index,int): raise RuntimeError('Dobot did not return a queued command index')
        deadline=time.monotonic()+timeout; stable=0; last_error='Queue has not completed'
        try:
            while time.monotonic()<deadline:
                self.control.check()
                if self.arm.cmds.current_index()>=index:
                    pose=self.pose(); reached=True
                    if target is not None:
                        xyz_error=math.dist([float(pose[k]) for k in ('x','y','z')],target[:3])
                        rotation_error=abs((float(pose['r'])-target[3]+180)%360-180)
                        reached=xyz_error<=self.s.position_tolerance and rotation_error<=self.s.rotation_tolerance
                        last_error=f'Target error: XYZ {xyz_error:.2f} mm, R {rotation_error:.2f} degrees'
                    stable=stable+1 if reached else 0
                    if stable>=2: return
                else: stable=0
                self.control.wait(.1)
            raise TimeoutError(f'Robot command did not settle within its deadline. {last_error}')
        except Exception:
            self.stop(); raise
    def home(self):
        self.control.check(); self.arm.cmds.queue_start()
        self._wait_index(self.arm.home(wait=False),self.s.home_timeout,(200.0,0.0,0.0,0.0))
        self.homed=True
    def move(self,pose):
        if not self.homed: raise RuntimeError('Home the robot in Manual robot before moving')
        target=tuple(pose) if len(pose)==4 else (*pose,self.s.tool_r)
        self.s.validate_pose(target); self.control.check()
        from dobotkit import PTPMode
        self.arm.set_speed(self.s.robot_velocity,self.s.robot_acceleration)
        index=self.arm.move_to(*target,mode=PTPMode.MOVL_XYZ,wait=False)
        self._wait_index(index,self.s.motion_timeout,target)
    def grip(self,closed):
        self.control.check()
        self.arm.effector.grip(bool(closed),queued=False)
        self.holding=bool(closed)  # Commanded state; not a pickup sensor.
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
