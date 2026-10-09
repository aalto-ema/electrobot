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
        self.s=settings; self.control=control; self.holding=False
    def move(self,pose):
        self.control.wait(.8/self.s.simulation_speed)
    def grip(self,closed):
        self.control.wait(.4/self.s.simulation_speed); self.holding=closed

class SimPotentiostat:
    def measure(self,s,index,control,point):
        previous=0
        for t,e,direction in s.potential_points():
            control.wait((t-previous)/s.simulation_speed)
            previous=t
            # Demonstration curve only; not a chemistry model.
            current=(direction*5 + 45*math.exp(-((e-.18)/.09)**2) if direction>0
                     else -5-40*math.exp(-((e+.12)/.10)**2))*(1+.04*index)
            point(t,e,current)

class Experiment:
    def __init__(self,s,control,event,point,output=Path('runs')):
        self.s=s.validate(); self.control=control; self.event=event; self.point=point
        self.output=Path(output)
    def run(self):
        s=self.s; robot=SimRobot(s,self.control); pot=SimPotentiostat()
        folder=self.output/(datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        folder.mkdir(parents=True)
        (folder/'settings.json').write_text(json.dumps(asdict(s),indent=2))
        log=[]; status='completed'; electrode=None
        def emit(state,detail):
            entry={'time':datetime.now().isoformat(),'electrode':electrode,'state':state,'detail':detail}
            log.append(entry); self.event(entry)
        def travel(x,y,z):
            # Raise at the current station before crossing to another station.
            robot.move((x,y,s.safe_z)); robot.move((x,y,z))
        def lift(x,y): robot.move((x,y,s.safe_z))
        try:
            for electrode in range(1,s.electrodes+1):
                self.control.check()
                x=s.rack_x+((electrode-1)%s.rack_columns)*s.rack_pitch
                y=s.rack_y+((electrode-1)//s.rack_columns)*s.rack_pitch
                emit('pickup',f'Picking up electrode {electrode} from its rack slot')
                travel(x,y,s.rack_z); robot.grip(True); lift(x,y)
                emit('insert','Seating carrier in cell; dry contact assumed in simulation')
                travel(s.cell_x,s.cell_y,s.cell_z); robot.grip(False); lift(s.cell_x,s.cell_y)
                self.control.wait(s.settle/s.simulation_speed)
                emit('measure','Running synthetic cyclic voltammetry')
                with (folder/f'electrode-{electrode:03d}.csv').open('w',newline='') as f:
                    writer=csv.writer(f); writer.writerow(['time_s','potential_V','current_uA','synthetic'])
                    def sample(t,e,i):
                        writer.writerow([t,e,i,True]); self.point(electrode,t,e,i)
                    pot.measure(s,electrode,self.control,sample)
                emit('retrieve','Retrieving carrier after simulated cell disconnect')
                travel(s.cell_x,s.cell_y,s.cell_z); robot.grip(True); lift(s.cell_x,s.cell_y)
                for dip in range(s.rinse_dips):
                    emit('rinse',f'Rinse dip {dip+1} of {s.rinse_dips}')
                    travel(s.rinse_x,s.rinse_y,s.rinse_z)
                    self.control.wait(s.rinse_dwell/s.simulation_speed); lift(s.rinse_x,s.rinse_y)
                emit('return','Returning electrode to its original slot')
                travel(x,y,s.rack_z); robot.grip(False); lift(x,y)
                emit('done',f'Electrode {electrode} completed')
        except Cancelled:
            status='stopped'; emit('stopped','Simulation stopped; no automatic recovery movement')
        except Exception as exc:
            status='failed'; emit('failed',str(exc)); raise
        finally:
            (folder/'events.json').write_text(json.dumps(log,indent=2))
            (folder/'summary.json').write_text(json.dumps({'mode':'simulation','status':status,
                 'holding_electrode':robot.holding,'last_electrode':electrode},indent=2))
        return folder,status
