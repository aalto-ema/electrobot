import json,math,tempfile,unittest
from pathlib import Path
from electrobot.config import Settings
from electrobot.rack_cad import export_rack
from electrobot.mesh_utils import connected_solids


class RackTests(unittest.TestCase):
    def test_radial_slot_mapping(self):
        s=Settings(rack_layout='radial',rack_columns=4,rack_radius=180,rack_start_angle=0,rack_angle_step=10)
        self.assertEqual(s.rack_pose(1),(180,0,s.rack_z))
        self.assertAlmostEqual(math.hypot(*s.rack_pose(4)[:2]),180)
        self.assertAlmostEqual(math.degrees(math.atan2(s.rack_pose(4)[1],s.rack_pose(4)[0])),30)
        self.assertEqual(s.rack_pose(5),(202,0,s.rack_z))
        self.assertEqual(len(s.rack_export_positions()),4)
        self.assertTrue(any('Rack slots need' in m for _,m in Settings(rack_layout='radial',rack_angle_step=1).calibration_issues()))
        with self.assertRaises(ValueError): Settings(rack_layout='radial',rack_columns=20,rack_angle_step=20).validate()

    def test_rectangular_and_radial_racks_export_connected_mesh(self):
        import trimesh
        for layout in ('rectangular','radial'):
            with self.subTest(layout=layout),tempfile.TemporaryDirectory() as d:
                s=Settings(rack_layout=layout,rack_columns=3,electrodes=5,rack_angle_step=10)
                mesh=trimesh.load_mesh(export_rack(s,d))
                self.assertTrue(mesh.is_watertight and mesh.is_volume)
                self.assertEqual(connected_solids(mesh),1)
                self.assertAlmostEqual(mesh.bounds[0][2],0)
                self.assertAlmostEqual(mesh.bounds[1][2],s.rack_post_height+s.rack_base_thickness)
                meta=json.loads(Path(d,'rack_manifest.json').read_text())
                self.assertEqual(len(meta['slot_robot_xyz']),6)
                for i,(global_xyz,local_xy) in enumerate(zip(meta['slot_robot_xyz'],meta['slot_local_xy']),1):
                    self.assertEqual(global_xyz,list(s.rack_pose(i)))
                    for axis in range(2): self.assertAlmostEqual(global_xyz[axis],local_xy[axis]+meta['robot_xy_at_stl_origin'][axis],places=3)
                self.assertTrue(Path(d,'electrode_rack.scad').exists())

    def test_tip_clearance_and_floor_are_required(self):
        for kwargs in ({'rack_socket_depth':25},{'rack_socket_depth':70},{'rack_socket_wall':1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): Settings(**kwargs).validate()
