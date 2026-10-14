"""Check printable interfaces, clearances and assembly transforms, without hardware."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh as tm

from electrobot.fixed_contact_cad import parts, metal_parts, interface, export, box, cylinder, wire_routes
from electrobot.mesh_utils import connected_solids


class FixedContactCADTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((Path(__file__).resolve().parents[1]/'cad/fixed-contact-prototype/dimensions.json').read_text())
        cls.meshes = parts(cls.d)

    def assert_clear(self, first, second):
        overlap = tm.boolean.intersection([first, second], engine='manifold')
        self.assertLess(abs(overlap.volume), 1e-4)

    def test_closed_connected_parts_and_metal_interfaces(self):
        d = self.d; meshes = self.meshes; fit = interface(d)
        ring, bars = metal_parts(d)
        for name, mesh in meshes.items():
            with self.subTest(part=name):
                self.assertTrue(mesh.is_watertight and mesh.is_volume)
                self.assertEqual(connected_solids(mesh), 1)
        for half in (meshes['holder_rear'], meshes['holder_front']):
            self.assert_clear(half, cylinder(d['electrode_diameter'], d['holder_height']+2, d['holder_height']/2))
            self.assert_clear(half, cylinder(d['wire_max_od'], d['holder_height']+2, d['holder_height']/2, y=d['holder_wire_y']))
            for sign in (-1, 1):
                self.assert_clear(half, cylinder(3, 30, d['bolt_z'], axis='y', x=sign*d['bolt_x']))
                nut = tm.creation.cylinder(radius=5.5/np.sqrt(3), height=2.4, sections=6)
                nut.apply_transform(tm.transformations.rotation_matrix(np.pi/2, [1, 0, 0]))
                nut.apply_translation([sign*d['bolt_x'], d['bolt_flat_y']-d['nut_depth']/2+.05, d['bolt_z']])
                self.assert_clear(half, nut)
                self.assert_clear(half, cylinder(6, .5, d['bolt_z'], axis='y', x=sign*d['bolt_x'], y=-d['bolt_flat_y']-.25))
            assembled = half.copy(); assembled.apply_translation([0, 0, fit['holder_bottom_z_mm']])
            self.assert_clear(assembled, ring)
            for lift in (0, .5, 3, 10, 20):
                raised = assembled.copy(); raised.apply_translation([0, 0, lift])
                self.assert_clear(raised, meshes['contact_insert'])
                for bar in bars:
                    self.assert_clear(raised, bar)
        for bar in bars:
            self.assert_clear(bar, meshes['contact_insert'])
            # A thin vertical overlap tests that each bar actually meets a finite
            # area of the annular washer, rather than only touching an edge.
            raised_bar = bar.copy(); raised_bar.apply_translation([0, 0, .05])
            patch = tm.boolean.intersection([ring, raised_bar], engine='manifold')
            self.assertGreater(patch.volume/.05, 8)
        self.assert_clear(ring, meshes['contact_insert'])
        self.assertAlmostEqual(fit['flange_to_insert_rim_gap_mm'], 1.8)
        self.assertGreater(fit['estimated_tip_clearance_above_bench_mm'], 10)

    def test_stand_cover_and_wire_routes(self):
        d = self.d; meshes = self.meshes; fit = interface(d)
        insert = meshes['contact_insert'].copy(); insert.apply_translation([0, 0, fit['insert_on_stand_z_mm']])
        self.assert_clear(insert, meshes['bench_stand'])
        cover = meshes['wire_cover'].copy(); cover.apply_translation([0, 0, -d['cover_thickness']])
        self.assert_clear(cover, meshes['contact_insert'])
        cover.apply_translation([0, 0, fit['insert_on_stand_z_mm']])
        self.assert_clear(cover, meshes['bench_stand'])
        rod = cylinder(d['electrode_diameter'], 100, 30)
        for mesh in (insert, cover, meshes['bench_stand']):
            self.assert_clear(mesh, rod)
        # Validate continuous symmetric channels and tail vias, not just their mouths.
        for route in wire_routes(d):
            self.assert_clear(route, meshes['contact_insert'])
        for side in (-1, 1):
            self.assert_clear(cylinder(d['wire_max_od'], 4, 2, x=side*d['wire_route_radius']), meshes['contact_insert'])
        self.assert_clear(box([4.8, 3.8, 1.8], [0, -d['wire_route_radius'], .9]), meshes['contact_insert'])

    def test_export_restores_assembly_and_print_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = export(self.d, folder)
            self.assertEqual(manifest['plate_solids'], 9)
            for entry in manifest['parts']:
                mesh = tm.load_mesh(Path(folder)/entry['file'])
                self.assertAlmostEqual(mesh.bounds[0, 2], 0, places=5)
                self.assertTrue(mesh.is_volume)
                bottom_area = mesh.area_faces[mesh.face_normals[:, 2] < -.999].sum()
                self.assertGreater(bottom_area, 10)
                mesh.apply_transform(np.linalg.inv(np.array(entry['assembly_to_print'])))
                original = self.meshes[Path(entry['file']).stem]
                np.testing.assert_allclose(mesh.bounds, original.bounds, atol=1e-5)
                np.testing.assert_allclose(mesh.center_mass, original.center_mass, atol=1e-5)
            plate = tm.load_mesh(Path(folder)/'complete_print_plate.stl')
            self.assertEqual(connected_solids(plate), 9)
            for axis, limit in enumerate([*self.d['printer_bed'], self.d['printer_height']]):
                self.assertLess(plate.bounds[1, axis], limit)
            coupons = tm.load_mesh(Path(folder)/'coupons_print_plate.stl')
            self.assertEqual(connected_solids(coupons), 4)
            self.assertEqual(manifest['geometry_id'], json.loads((Path(folder)/'manifest.json').read_text())['geometry_id'])

    def test_rejects_incompatible_interfaces(self):
        for change in ({'insert_id':17}, {'bar_seat_depth':1.2}, {'wire_hole':1.2},
                       {'insert_height':17}, {'stand_height':30}, {'bolt_x':3}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                parts(dict(self.d, **change))
