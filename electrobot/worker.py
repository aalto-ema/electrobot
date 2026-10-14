"""One serialized device owner; GUI only submits commands or sets cancel events."""
import queue
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from .engine import Control,Cancelled,Experiment,SimRobot,SimPotentiostat
from .drivers import DobotRobot,PalmSensPotentiostat

class DeviceWorker(QThread):
    state=Signal(dict); pose=Signal(dict); event=Signal(dict); diagnostic=Signal(dict)
    point=Signal(int,float,float,float); result=Signal(str,str)
    completed=Signal(str,bool,str)
    def __init__(self,output):
        super().__init__(); self.output=Path(output); self.commands=queue.Queue()
        self.control=Control(); self.robot=None; self.pot=None
        self.robot_connected=False; self.pot_connected=False; self.mode='simulation'
    def submit(self,command,settings,payload=None):
        control=Control(); self.control=control
        self.commands.put((command,settings,payload,control))
    def cancel(self):
        self.control.cancel.set(); self.control.resume.set()
    def shutdown(self):
        self.cancel(); self.commands.put(('shutdown',None,None,None))
    def emit_pose(self,pose):
        self.pose.emit(pose); self.publish()
    def publish(self):
        self.state.emit({'mode':self.mode,'robot':self.robot_connected,'potentiostat':self.pot_connected,
            'homed':bool(self.robot and self.robot.homed),
            'holding':bool(self.robot and self.robot.holding),
            'gripper_state':self.robot.gripper_state if self.robot_connected else 'unknown',
            'potentiostat_name':self.pot.name if self.pot_connected else 'Disconnected'})
    def close_devices(self):
        errors=[]
        for attr,flag in (('pot','pot_connected'),('robot','robot_connected')):
            device=getattr(self,attr)
            if device:
                try: device.disconnect()
                except Exception as exc: errors.append(f'{attr}: {exc}')
            setattr(self,attr,None); setattr(self,flag,False)
        if errors: raise RuntimeError('; '.join(errors))
    def setup(self,s,control):
        if self.robot is None or self.mode!=s.mode:
            self.close_devices(); self.mode=s.mode
            if s.mode=='simulation':
                self.robot=SimRobot(s,control); self.pot=SimPotentiostat(s)
                self.robot_connected=True; self.pot_connected=True
            else:
                self.robot=DobotRobot(s,control); self.pot=PalmSensPotentiostat(s)
            self.robot.pose_callback=self.emit_pose
            self.robot.diagnostic_callback=self.diagnostic.emit
            self.diagnostic.emit(dict(self.robot.diagnostics))
        self.robot.s=s; self.robot.control=control; self.pot.s=s
    def run(self):
        while True:
            try: command,s,payload,control=self.commands.get(timeout=.5)
            except queue.Empty:
                if self.mode=='hardware' and self.robot_connected:
                    try: self.robot.poll_health(); self.publish()
                    except Exception: self.pose.emit({})  # Hide unavailable feedback; retry next idle poll.
                continue
            if command=='shutdown':
                try: self.close_devices()
                except Exception as exc: self.completed.emit(command,False,str(exc))
                self.publish(); return
            ok=True; message=''
            try:
                if command!='rehearsal_pose': s.validate()
                self.setup(s,control); control.check()
                if command=='configure':
                    if self.robot_connected: self.robot.pose()
                elif command=='connect_robot':
                    self.robot.connect(); self.robot_connected=True
                elif command=='connect_potentiostat':
                    self.pot.connect(); self.pot_connected=True
                elif command=='disconnect':
                    self.close_devices()
                elif command in ('run','rehearse'):
                    if not self.robot_connected or (command=='run' and not self.pot_connected):
                        raise RuntimeError('Connect the robot before rehearsal' if command=='rehearse' else 'Connect both the robot and potentiostat before starting a batch')
                    folder,status=Experiment(s,control,self.event.emit,self.point.emit,self.output,
                        self.robot,self.pot if self.pot_connected else None,rehearsal=command=='rehearse').run()
                    self.result.emit(str(folder),status)
                    if status=='failed':
                        ok=False; message=getattr(self.robot,'diagnostics',{}).get('fault') or 'Batch failed; see Activity and the saved run events.'
                else:
                    if not self.robot_connected: raise RuntimeError('Connect the robot first')
                    if command=='home': self.robot.home()
                    elif command in ('pose','rehearsal_pose'): self.robot.pose()
                    elif command=='move': self.robot.move(payload)
                    elif command=='jog':
                        pose=self.robot.pose(); target=[pose[k] for k in ('x','y','z','r')]
                        axis,delta=payload; target[axis]+=delta; self.robot.move(target)
                    elif command=='grip': self.robot.grip(payload)
                    elif command=='open_fully': self.robot.open_fully()
                    elif command=='check_route':
                        if self.mode!='hardware': raise ValueError('Controller route check requires Hardware mode and a connected robot')
                        pose=self.robot.pose()
                        self.robot.preflight_route(s.planned_route(tuple(pose[k] for k in ('x','y','z','r'))))
                    elif command=='clear_alarms': self.robot.clear_alarms()
                    elif command=='stop': self.robot.stop()
                    else: raise ValueError(f'Unknown command: {command}')
                    if command!='stop': self.robot.pose()
            except Cancelled:
                ok=False; message='Stopped'
                if self.robot_connected:
                    try: self.robot.stop()
                    except Exception as exc: message+=f'; stop failed: {exc}'
            except Exception as exc:
                ok=False; message=str(exc)
                if command in ('home','move','jog','grip','open_fully','run','rehearse') and self.robot_connected:
                    try: self.robot.stop()
                    except Exception as cleanup: message+=f'; stop failed: {cleanup}'
            finally:
                self.publish(); self.completed.emit(command,ok,message)
