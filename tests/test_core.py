import csv
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from electrobot.config import Settings
from electrobot.engine import Experiment,Control,Cancelled,SimRobot

class CoreTests(unittest.TestCase):
    def test_calibration_reports_multiple_conflicts(self):
        s=Settings(safe_z=10,cell_x=350,workspace_y_min=100,workspace_y_max=-100)
        messages=[message for _,message in s.calibration_issues()]
        self.assertTrue(any('Y minimum' in m for m in messages))
        self.assertTrue(any('Travel Z must' in m for m in messages))
        self.assertTrue(any('Cell X' in m for m in messages))
        self.assertTrue(any('Cell radius' in m for m in messages))
        self.assertEqual(Settings().calibration_issues(),[])

    def test_robot_rehearsal_without_potentiostat(self):
        with tempfile.TemporaryDirectory() as d:
            s=Settings(mode='hardware',calibrated=True,fixture_verified=True,electrodes=1,settle=0,rinse_dwell=0)
            c=Control(); robot=SimRobot(s,c); grips=[]
            original=robot.grip
            robot.grip=lambda closed:(grips.append(closed),original(closed))
            # Keep the hardware timing path without waiting on a mock movement.
            robot.move=lambda pose:setattr(robot,'current_pose',dict(zip(('x','y','z','r'),(*pose[:3],s.tool_r))))
            events=[]
            folder,status=Experiment(s,c,events.append,lambda *a:self.fail('Rehearsal emitted measurement data'),d,robot=robot,rehearsal=True).run()
            self.assertEqual(status,'completed')
            self.assertEqual(grips,[False,True,False,True,False])
            self.assertFalse(list(folder.glob('*.csv')))
            self.assertIn('wait',[e['state'] for e in events])
            summary=json.loads((folder/'summary.json').read_text())
            self.assertEqual(summary['run_type'],'robot_rehearsal')
            self.assertFalse(summary['measurement_performed'])

    def test_rehearsal_never_calls_measurement(self):
        class Pot:
            def cell_off(self): pass
            def validate_protocol(self,s): raise AssertionError('Method validation called')
            def measure(self,*a,**kw): raise AssertionError('Measurement called')
        with tempfile.TemporaryDirectory() as d:
            s=Settings(electrodes=1,simulation_speed=10000,settle=0,rinse_dwell=0)
            _,status=Experiment(s,Control(),lambda e:None,lambda *a:None,d,potentiostat=Pot(),rehearsal=True).run()
            self.assertEqual(status,'completed')

    def test_cv_timing_and_vertices(self):
        s=Settings().validate(); points=s.potential_points()
        self.assertAlmostEqual(points[-1][0],40)
        self.assertEqual(points[-1][1],0)
        self.assertEqual(sum(1 for _,e,_ in points if abs(e-.5)<1e-9),2)
        self.assertEqual(sum(1 for _,e,_ in points if abs(e+.5)<1e-9),2)
        self.assertTrue(all(0<=b[1]-a[1]<=s.step_v+1e-8 or 0<=a[1]-b[1]<=s.step_v+1e-8 for a,b in zip(points,points[1:])))
    def test_invalid_geometry_and_protocol(self):
        for kwargs in ({'scan_rate':0},{'vertex1_v':4},{'funnel_diameter':13},
                       {'safe_z':10},{'port_offset':4},{'immersion':60},{'step_v':0},
                       {'current_range_ua':200},{'rinse_dwell':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): Settings(**kwargs).validate()
    def test_batch_sequence_and_exports(self):
        with tempfile.TemporaryDirectory() as d:
            events=[]; points=[]
            s=Settings(simulation_speed=10000,settle=0,rinse_dwell=0)
            folder,status=Experiment(s,Control(),events.append,lambda *v:points.append(v),d).run()
            self.assertEqual(status,'completed')
            self.assertEqual([e['electrode'] for e in events if e['state']=='done'],[1,2,3])
            self.assertEqual(len([e for e in events if e['state']=='rinse']),9)
            for i in range(1,4):
                states=[e['state'] for e in events if e['electrode']==i]
                self.assertEqual(states,['pickup','insert','measure','retrieve','rinse','rinse','rinse','return','done'])
                with (folder/f'electrode-{i:03d}.csv').open() as f:
                    rows=list(csv.DictReader(f)); self.assertEqual(len(rows),len(s.potential_points()))
                    self.assertEqual(rows[-1]['synthetic'],'True')
            self.assertFalse(json.loads((folder/'summary.json').read_text())['holding_electrode'])
    def test_cancel_preserves_partial_measurement(self):
        with tempfile.TemporaryDirectory() as d:
            c=Control(); count=0
            def sample(*args):
                nonlocal count
                count+=1
                if count==5: c.cancel.set()
            folder,status=Experiment(Settings(electrodes=1,simulation_speed=10000),c,lambda e:None,sample,d).run()
            self.assertEqual(status,'stopped')
            with (folder/'electrode-001.csv').open() as f: self.assertEqual(len(list(csv.DictReader(f))),5)
            self.assertEqual(json.loads((folder/'summary.json').read_text())['status'],'stopped')
    def test_cancel_while_paused(self):
        c=Control(); c.resume.clear(); result=[]
        def wait():
            try: c.check()
            except Cancelled: result.append('cancelled')
        t=threading.Thread(target=wait); t.start(); time.sleep(.02); self.assertTrue(t.is_alive())
        c.cancel.set(); t.join(1); self.assertEqual(result,['cancelled'])
    def test_mesh_closed_and_dimensions(self):
        from electrobot.cad import export_cap
        import trimesh
        with tempfile.TemporaryDirectory() as d:
            mesh=trimesh.load(export_cap(Settings(),d))
            self.assertTrue(mesh.is_watertight); self.assertTrue(mesh.is_volume)
            adjacency={i:set() for i in range(len(mesh.faces))}
            for a,b in mesh.face_adjacency:
                adjacency[int(a)].add(int(b)); adjacency[int(b)].add(int(a))
            seen=set(); stack=[0]
            while stack:
                face=stack.pop()
                if face in seen: continue
                seen.add(face); stack.extend(adjacency[face]-seen)
            self.assertEqual(len(seen),len(mesh.faces))
            self.assertAlmostEqual(mesh.extents[0],59.8,places=4)
            self.assertAlmostEqual(mesh.extents[2],10,places=4)

if __name__=='__main__': unittest.main()
