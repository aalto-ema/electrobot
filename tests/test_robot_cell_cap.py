"""Geometry-only checks for the provisional glass-cell cap; no hardware."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh as tm

from electrobot.robot_cell_cap import build_parts, export, stack_interfaces, at, helical_thread
from electrobot.fixed_contact_cad import cylinder, box, metal_parts, insert as contact_insert
from electrobot.mesh_utils import connected_solids


class RobotCellCapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.d=json.loads((root/'cad/robot-cell-cap/dimensions.json').read_text())
        cls.contact=json.loads((root/'cad/fixed-contact-prototype/dimensions.json').read_text())
        cls.contact['insert_flange_od']=cls.d['compact_insert_flange_diameter']
        cls.meshes=build_parts(cls.d,cls.contact)

    def assert_clear(self,a,b):
        overlap=tm.boolean.intersection([a,b],engine='manifold')
        self.assertLess(abs(overlap.volume),1e-4)

    def test_closed_parts_printed_interface_and_all_electrode_paths(self):
        d=self.d; c=self.contact; m=self.meshes; fit=stack_interfaces(d,c)
        for name,mesh in m.items():
            with self.subTest(part=name):
                self.assertTrue(mesh.is_watertight and mesh.is_volume)
                self.assertEqual(connected_solids(mesh),1)
        self.assert_clear(m['upper_deck'],m['threaded_base'])
        mounted={}
        for name,z in [('compact_contact_insert',fit['insert_origin_z_mm']),
                       ('wire_cover',fit['cover_bottom_z_mm']),
                       ('holder_rear',fit['holder_origin_z_mm']),('holder_front',fit['holder_origin_z_mm'])]:
            mounted[name]=at(m[name],[*d['we_xy'],z])
            for fixed in (m['upper_deck'],m['threaded_base']):
                self.assert_clear(mounted[name],fixed)
        for a,b in [('compact_contact_insert','wire_cover'),('compact_contact_insert','holder_rear'),
                    ('compact_contact_insert','holder_front'),('holder_rear','holder_front')]:
            self.assert_clear(mounted[a],mounted[b])
        # Fixed RE/CE stems pass beside the compact insert, not through its flange.
        for xy in d['fixed_electrode_xy']:
            stem=cylinder(7,80,15,x=xy[0],y=xy[1])
            head=cylinder(d['fixed_fitting_head_envelope_diameter'],d['fixed_fitting_head_height'],d['fixed_fitting_head_height']/2,x=xy[0],y=xy[1])
            for mesh in [m['upper_deck'],m['threaded_base'],*mounted.values()]:
                self.assert_clear(stem,mesh)
            for mesh in [m['upper_deck'],*mounted.values()]: self.assert_clear(head,mesh)
        for xy in d['gas_xy']:
            tube=cylinder(d['gas_bore'],80,15,x=xy[0],y=xy[1])
            for mesh in [m['upper_deck'],m['threaded_base'],*mounted.values()]:
                self.assert_clear(tube,mesh)
        rod=cylinder(c['electrode_diameter'],100,15,x=d['we_xy'][0],y=d['we_xy'][1])
        for mesh in [m['upper_deck'],m['threaded_base'],*mounted.values()]: self.assert_clear(rod,mesh)
        # A straight insertion check includes the unchanged split holder and ring.
        ring,_=metal_parts(c)
        ring=at(ring,[*d['we_xy'],fit['insert_origin_z_mm']])
        for lift in (0,.5,3,10,20):
            for name in ('holder_rear','holder_front'):
                raised=at(mounted[name],[0,0,lift])
                for mesh in (m['upper_deck'],mounted['compact_contact_insert']): self.assert_clear(raised,mesh)
            self.assert_clear(at(ring,[0,0,lift]),mounted['compact_contact_insert'])
        old_contact=dict(c,insert_flange_od=38)
        old=at(contact_insert(old_contact),[*d['we_xy'],fit['insert_origin_z_mm']])
        xy=d['fixed_electrode_xy'][0]
        overlap=tm.boolean.intersection([old,cylinder(7,80,15,x=xy[0],y=xy[1])],engine='manifold')
        self.assertGreater(overlap.volume,1e-4)
        self.assertAlmostEqual(m['threaded_base'].bounds[0,2],-15,places=5)
        self.assertAlmostEqual(fit['cover_to_deck_gap_mm'],.5)
        self.assertAlmostEqual(fit['estimated_we_tip_z_mm'],-22.9)

    def test_fasteners_gasket_floor_and_cable_exit(self):
        d=self.d;m=self.meshes
        for xy in d['mount_bolt_xy']:
            nut=tm.creation.cylinder(radius=5.5/math.sqrt(3),height=2.4,sections=6)
            nut.apply_transform(tm.transformations.rotation_matrix(math.atan2(xy[1],xy[0])+math.pi/6,[0,0,1]))
            nut.apply_translation([*xy,-1.4])
            self.assert_clear(nut,m['threaded_base'])
            bolt=cylinder(3,10,1.5,x=xy[0],y=xy[1])  # shaft -3.5 .. +6.5
            self.assert_clear(bolt,m['threaded_base']);self.assert_clear(bolt,m['upper_deck'])
            washer=cylinder(6,.5,6.25,x=xy[0],y=xy[1])
            self.assert_clear(washer,m['upper_deck'])
        # Blind nut/bolt pockets retain >=1 mm of unbroken underside flange.
        self.assertGreaterEqual(d['base_plate_thickness']-d['mount_blind_depth'],1)
        cable=box([1.4,9,1.4],[d['we_xy'][0],-d['we_pedestal_diameter']/2,8.4])
        self.assert_clear(cable,m['upper_deck'])

    def test_thread_is_helical_not_stacked_rings(self):
        mesh=helical_thread(43,2,.8,10,1)
        self.assertTrue(mesh.is_volume and mesh.is_watertight)
        self.assertEqual(connected_solids(mesh),1)
        crest=box([.12,.12,.12],[21.4,0,4.1])
        valley=box([.12,.12,.12],[-21.4,0,4.1])
        self.assertGreater(tm.boolean.intersection([mesh,crest],engine='manifold').volume,.0005)
        self.assert_clear(mesh,valley)

    def test_export_transform_bed_and_plate_components(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest=export(self.d,self.contact,folder)
            self.assertEqual(manifest['plate_solids'],12)
            for entry in manifest['parts']:
                mesh=tm.load_mesh(Path(folder)/entry['file'])
                self.assertTrue(mesh.is_watertight and mesh.is_volume)
                self.assertEqual(connected_solids(mesh),1)
                self.assertAlmostEqual(mesh.bounds[0,2],0,places=5)
                self.assertGreater(mesh.area_faces[mesh.face_normals[:,2]<-.999].sum(),10)
                mesh.apply_transform(np.linalg.inv(np.array(entry['assembly_to_print'])))
                original=self.meshes[Path(entry['file']).stem]
                np.testing.assert_allclose(mesh.bounds,original.bounds,atol=1e-5)
                np.testing.assert_allclose(mesh.center_mass,original.center_mass,atol=1e-5)
            assembly=tm.load_mesh(Path(folder)/'cap_assembly_print_plate.stl')
            self.assertTrue(assembly.is_watertight and assembly.is_volume)
            self.assertEqual(connected_solids(assembly),6)
            gauges=tm.load_mesh(Path(folder)/'gauges_print_plate.stl')
            self.assertTrue(gauges.is_watertight and gauges.is_volume)
            self.assertEqual(connected_solids(gauges),6)
            complete=tm.load_mesh(Path(folder)/'complete_print_plate.stl')
            self.assertTrue(complete.is_watertight and complete.is_volume)
            for i,limit in enumerate([*self.d['printer_bed'],self.d['printer_height']]):
                self.assertLess(manifest['plate_bounds_mm'][1][i],limit)

    def test_rejects_incompatible_layout(self):
        for change in ({'flange_diameter':50},{'we_socket_rise':10},{'gas_xy':[[9,8],[9,-8]]},
                       {'fixed_electrode_xy':[[0,0],[0,10]]},{'mount_blind_depth':5}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                build_parts(dict(self.d,**change),self.contact)
