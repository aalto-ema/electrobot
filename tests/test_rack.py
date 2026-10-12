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

    def test_lattice_exports_reusable_top_and_separate_feet(self):
        import trimesh
        for layout in ('rectangular','radial'):
            with self.subTest(layout=layout),tempfile.TemporaryDirectory() as d:
                s=Settings(rack_design='lattice',rack_layout=layout,rack_columns=4,electrodes=8,rack_pitch=36,rack_angle_step=11)
                export_rack(s,d); meta=json.loads(Path(d,'rack_manifest.json').read_text())
                self.assertEqual(len(meta['modules']),2)
                self.assertEqual(meta['foot_quantity'],6); self.assertEqual(meta['holder_quantity'],8)
                self.assertAlmostEqual(meta['seat_height_mm']-s.rack_hanging_length,s.rack_tip_clearance)
                for part in meta['parts']:
                    mesh=trimesh.load_mesh(Path(d,part['file']))
                    self.assertTrue(mesh.is_watertight and mesh.is_volume)
                    self.assertEqual(connected_solids(mesh),1)
                    self.assertAlmostEqual(mesh.bounds[0][2],0)
                    self.assertTrue(part['fits_printer_xy'])
                tops=[p for p in meta['parts'] if p['file'].startswith('rack_top')]
                if layout=='rectangular': self.assertEqual(len(tops),1); self.assertEqual(tops[0]['quantity'],2)
                first=meta['modules'][0]
                rotation=trimesh.transformations.rotation_matrix(math.radians(first['rotation_deg']),[0,0,1])
                top=trimesh.load_mesh(Path(d,first['file'])); top.apply_transform(rotation); top.apply_translation([*first['robot_xy_at_stl_origin'],meta['foot_height_mm']])
                foot=trimesh.load_mesh(Path(d,'rack_foot.stl')); dims=s.lattice_dimensions()
                x,y=first['foot_centers_robot_xy'][0]
                foot.apply_translation([-dims['peg_offset']-dims['foot_radius'],-dims['foot_radius'],0]); foot.apply_transform(rotation); foot.apply_translation([x,y,0])
                overlap=trimesh.boolean.intersection([top,foot],engine='manifold')
                if len(overlap.faces):
                    import numpy as np
                    self.assertLess(abs(np.einsum('ij,ij->i',np.cross(overlap.triangles[:,0],overlap.triangles[:,1]),overlap.triangles[:,2]).sum()/6),.001)
                self.assertTrue(Path(d,'ASSEMBLY.md').exists())
                with tempfile.TemporaryDirectory() as small:
                    from dataclasses import replace
                    export_rack(replace(s,electrodes=4),small)
                    old=json.loads(Path(small,'rack_manifest.json').read_text())
                    self.assertEqual(old['modules'][0]['geometry_id'],first['geometry_id'])
                    self.assertEqual(Path(small,first['file']).read_bytes(),Path(d,first['file']).read_bytes())
                for instance in meta['modules']:
                    angle=math.radians(instance['rotation_deg']); c,t=math.cos(angle),math.sin(angle)
                    for (x,y),(gx,gy,gz) in zip(instance['slot_local_xy'],instance['slot_robot_xyz']):
                        ox,oy=instance['robot_xy_at_stl_origin']
                        self.assertAlmostEqual(ox+c*x-t*y,gx,places=3); self.assertAlmostEqual(oy+t*x+c*y,gy,places=3)

    def test_lattice_fit_and_bed_conflicts(self):
        for kwargs in ({'rack_deck_thickness':4},{'holder_rod_depth':20},{'rack_seat_depth':12},{'holder_flange_diameter':16},{'rack_hanging_length':50}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): Settings(rack_design='lattice',**kwargs).validate()
        self.assertTrue(any('Rack slots need' in m for _,m in Settings(rack_design='lattice').calibration_issues()))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'reduce slots/module'):
                export_rack(Settings(rack_design='lattice',rack_pitch=36,rack_columns=4,electrodes=4,rack_printer_width=40,rack_printer_depth=40),d)
            self.assertFalse(list(Path(d).glob('*.stl')))

    def test_radial_modules_reuse_rotated_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            s=Settings(rack_design='lattice',rack_layout='radial',rack_columns=8,electrodes=16,rack_pitch=36,rack_angle_step=11)
            export_rack(s,d); meta=json.loads(Path(d,'rack_manifest.json').read_text())
            tops=[p for p in meta['parts'] if p['file'].startswith('rack_top')]
            self.assertEqual(len(tops),2); self.assertEqual([p['quantity'] for p in tops],[2,2])
            self.assertEqual(meta['modules'][0]['geometry_id'],meta['modules'][1]['geometry_id'])
            self.assertNotEqual(meta['modules'][0]['rotation_deg'],meta['modules'][1]['rotation_deg'])
