"""Hardware-independent experiment sequence and explicitly synthetic CV data."""
import csv
import json
import math
import threading
import time
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

class Cancelled(Exception): pass

class Control:
    def __init__(self):
        self.cancel=threading.Event()
        self.resume=threading.Event(); self.resume.set()
    def check(self):
        while not self.resume.wait(0.05):
            if self.cancel.is_set(): raise Cancelled()
        if self.cancel.is_set(): raise Cancelled()
    def wait(self,seconds):
        remaining=seconds
        while remaining>0:
            self.check(); start=time.monotonic()
            self.cancel.wait(min(.05,remaining))
            remaining-=time.monotonic()-start
        self.check()

class SimRobot:
    def __init__(self,settings,control):
        self.s=settings; self.control=control; self.holding=False; self.homed=True; self.gripper_state='released'
        self.current_pose={'x':200.0,'y':0.0,'z':80.0,'r':0.0}; self.pose_callback=lambda p:None
    def move(self,pose):
        self.s.validate_pose(pose)
        target=dict(zip(('x','y','z','r'),(*pose,self.s.tool_r) if len(pose)==3 else pose))
        start=dict(self.current_pose)
        for step in range(1,11):
            self.control.wait(.08/self.s.simulation_speed)
            self.current_pose={k:start[k]+(target[k]-start[k])*step/10 for k in target}
            self.pose_callback(dict(self.current_pose))
    def grip(self,closed):
        self.control.wait(.4/self.s.simulation_speed); self.holding=closed
        self.gripper_state='closed' if closed else 'released'
    def open_fully(self):
        self.control.wait(.4/self.s.simulation_speed); self.holding=False; self.gripper_state='fully_open'

    def connect(self): self.pose_callback(self.current_pose)
    def disconnect(self): pass
    def pose(self): self.pose_callback(self.current_pose); return dict(self.current_pose)
    def home(self): self.move((200,0,80,0)); self.homed=True
    def stop(self): pass

class SimPotentiostat:
    name='Simulated EmStat4S LR'
    def __init__(self,s=None): self.s=s
    def connect(self): pass
    def disconnect(self): pass
    def cell_off(self): pass
    def validate_protocol(self,s): s.validate()

    def measure(self,s,index,control,point,stream=None):
        previous=0
        for t,e,direction in s.potential_points():
            control.wait((t-previous)/s.simulation_speed)
            previous=t
            # Demonstration curve only; not a chemistry model.
            current=(direction*5 + 45*math.exp(-((e-.18)/.09)**2) if direction>0
                     else -5-40*math.exp(-((e+.12)/.10)**2))*(1+.04*index)
            point(t,e,current)

class Experiment:
    def __init__(self,s,control,event,point,output=Path('runs'),robot=None,potentiostat=None,rehearsal=False):
        self.rehearsal=rehearsal
        self.s=s.validate(); self.control=control; self.event=event; self.point=point
        self.output=Path(output); self.robot=robot; self.potentiostat=potentiostat
    def run(self):
        s=self.s.validate_batch()
        if s.mode=='hardware' and (self.robot is None or (not self.rehearsal and self.potentiostat is None)):
            raise RuntimeError('Hardware requires connected robot and potentiostat; simulation fallback is disabled')
        robot=self.robot or SimRobot(s,self.control)
        pot=self.potentiostat if self.rehearsal else (self.potentiostat or SimPotentiostat(s))
        robot.s=s; robot.control=self.control
        if s.mode=='hardware' and robot.holding:
            raise RuntimeError('Secure/release the held electrode before a new hardware batch')
        if s.mode=='hardware' and not robot.homed:
            raise RuntimeError('Home the robot before starting a hardware batch')
        if not self.rehearsal: pot.validate_protocol(s)  # Fail before any movement if the method is incompatible.
        if s.mode=='hardware':
            initial=robot.pose()
            s.validate_pose(tuple(initial[k] for k in ('x','y','z','r')))
            s.validate_pose((initial['x'],initial['y'],s.safe_z,s.tool_r))
        synthetic=s.mode=='simulation'
        speed=s.simulation_speed if synthetic else 1.0
        folder=self.output/(datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        folder.mkdir(parents=True)
        (folder/'settings.json').write_text(json.dumps(asdict(s),indent=2))
        log=[]; status='completed'; electrode=None
        def emit(state,detail):
            entry={'time':datetime.now().isoformat(),'electrode':electrode,'state':state,'detail':detail}
            log.append(entry); self.event(entry)
        def travel(x,y,z):
            # Raise at the current station before crossing to another station.
            current=robot.pose()
            robot.move((current['x'],current['y'],s.safe_z))
            robot.move((x,y,s.safe_z)); robot.move((x,y,z))
        def lift(x,y): robot.move((x,y,s.safe_z))
        try:
            if pot is not None: pot.cell_off()
            if self.rehearsal: emit('rehearsal','Robot-only rehearsal: gripper actuates; no measurement or electrochemistry data')
            robot.grip(False)
            for electrode in range(s.first_electrode,s.first_electrode+s.electrodes):
                self.control.check()
                x,y,_=s.rack_pose(electrode)
                emit('pickup',f'Picking up electrode {electrode} from its rack slot')
                travel(x,y,s.rack_z); robot.grip(True); lift(x,y)
                emit('insert','Seating carrier in the cell fixture')
                travel(s.cell_x,s.cell_y,s.cell_z); robot.grip(False); lift(s.cell_x,s.cell_y)
                self.control.wait(s.settle/speed)
                if self.rehearsal:
                    emit('wait','Measurement omitted in robot-only rehearsal')
                else:
                    emit('measure','Running '+('synthetic' if synthetic else 'hardware')+' cyclic voltammetry')
                    with (folder/f'electrode-{electrode:03d}.csv').open('w',newline='') as f:
                        writer=csv.writer(f); writer.writerow(['time_s','potential_V','current_uA','synthetic','time_source'])
                        def sample(t,e,i):
                            if not all(math.isfinite(v) for v in (t,e,i)): raise ValueError('Potentiostat returned non-finite data')
                            writer.writerow([t,e,i,synthetic,'protocol' if synthetic else 'nominal_cv_step']); f.flush(); self.point(electrode,t,e,i)
                        pot.measure(s,electrode,self.control,sample,stream=folder/f'electrode-{electrode:03d}-sdk.jsonl' if not synthetic else None)
                    if pot is not None: pot.cell_off()
                emit('retrieve','Retrieving carrier after cell disconnect')
                travel(s.cell_x,s.cell_y,s.cell_z); robot.grip(True); lift(s.cell_x,s.cell_y)
                for dip in range(s.rinse_dips):
                    emit('rinse',f'Rinse dip {dip+1} of {s.rinse_dips}')
                    travel(s.rinse_x,s.rinse_y,s.rinse_z)
                    self.control.wait(s.rinse_dwell/speed); lift(s.rinse_x,s.rinse_y)
                emit('return','Returning electrode to its original slot')
                travel(x,y,s.rack_z); robot.grip(False); lift(x,y)
                emit('done',f'Electrode {electrode} completed')
        except Cancelled:
            status='stopped'; emit('stopped','Stopped; no automatic recovery movement')
        except Exception as exc:
            status='failed'; emit('failed',str(exc))
        finally:
            cleanup_errors=[]
            if status!='completed':
                try: robot.stop()
                except Exception as exc: cleanup_errors.append(f'Robot stop failed: {exc}')
            try:
                if pot is not None: pot.cell_off()
            except Exception as exc: cleanup_errors.append(f'Cell off failed: {exc}')
            for error in cleanup_errors: emit('cleanup_error',error)
            if cleanup_errors: status='failed'
            (folder/'events.json').write_text(json.dumps(log,indent=2))
            (folder/'summary.json').write_text(json.dumps({'run_type':'robot_rehearsal' if self.rehearsal else 'experiment','measurement_performed':not self.rehearsal,'mode':s.mode,'status':status,'run_name':s.run_name,'cleanup_errors':cleanup_errors,
                 'grip_state_is_commanded':True,'holding_electrode':robot.holding,'last_electrode':electrode},indent=2))
        return folder,status
