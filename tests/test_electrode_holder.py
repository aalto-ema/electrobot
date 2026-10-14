import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import trimesh as tm
from electrobot.electrode_holder import holder_halves,export_holder,cylinder
from electrobot.mesh_utils import connected_solids
from electrobot.config import Settings


class ElectrodeHolderTests(unittest.TestCase):
    def dimensions(self):
        return json.loads((Path(__file__).resolve().parents[1]/'cad/electrode-holder/dimensions.json').read_text())

    def test_closed_parts_bore_bolts_and_rack_interface(self):
        d=self.dimensions(); halves=holder_halves(d)
        rod=cylinder(d['electrode_body_diameter'],d['total_height']+2,d['total_height']/2)
        s=Settings()
        # Existing 18 mm rack seat: top is at pilot_height; pilot floor at zero.
        deck=cylinder(40,6,d['pilot_height']-3)
        seat=cylinder(s.holder_diameter+s.rack_holder_clearance,d['pilot_height']+.1,d['pilot_height']/2+.05)
        through=cylinder(s.rod_diameter+s.we_clearance,8,d['pilot_height']-3)
        fixture=tm.boolean.difference([deck,seat,through],engine='manifold')
        for half in halves:
            self.assertTrue(half.is_volume and half.is_watertight)
            self.assertEqual(connected_solids(half),1)
            for tool in (rod,fixture):
                overlap=tm.boolean.intersection([half,tool],engine='manifold')
                self.assertLess(abs(overlap.volume),.001)
            for sign in (-1,1):
                bolt=cylinder(3.,30,d['bolt_z'],axis='y',x=sign*d['bolt_x'])
                overlap=tm.boolean.intersection([half,bolt],engine='manifold')
                self.assertLess(abs(overlap.volume),.001)
        for sign in (-1,1):
            nut=tm.creation.cylinder(radius=5.5/np.sqrt(3),height=2.4,sections=6)
            nut.apply_transform(tm.transformations.rotation_matrix(np.pi/2,[1,0,0]))
            nut.apply_translation([sign*d['bolt_x'],d['bolt_flat_y']-d['nut_depth']/2+.05,d['bolt_z']])
            for half in halves:
                overlap=tm.boolean.intersection([half,nut],engine='manifold')
                self.assertLess(abs(overlap.volume),.001)
            washer=cylinder(6,.5,d['bolt_z'],axis='y',x=sign*d['bolt_x'],y=-d['bolt_flat_y']-.25)
            for half in halves:
                overlap=tm.boolean.intersection([half,washer],engine='manifold')
                self.assertLess(abs(overlap.volume),.001)
        self.assertEqual(d['pilot_diameter'],s.holder_diameter)
        self.assertEqual(d['pilot_height'],s.rack_seat_depth)

    def test_export_print_orientation_and_reproducible_assembly(self):
        d=self.dimensions()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); manifest=export_holder(d,path)
            self.assertEqual(manifest['estimated_hanging_below_deck_mm'],41.5)
            self.assertEqual(manifest['print_plate_solids'],2)
            for part,original in zip(manifest['parts'],holder_halves(d)):
                mesh=tm.load_mesh(path/part['file'])
                self.assertAlmostEqual(mesh.bounds[0,2],0)
                self.assertGreater(mesh.area_faces[abs(mesh.face_normals[:,2]+1)<1e-5].sum(),100)
                # Invert the documented print transform to recover assembly frame.
                mesh.apply_translation(-np.array(part['print_origin_translation_mm']))
                mesh.apply_transform(tm.transformations.rotation_matrix(
                    -np.radians(part['print_rotation_x_deg']),[1,0,0]))
                np.testing.assert_allclose(mesh.bounds,original.bounds,atol=1e-5)
            self.assertEqual(connected_solids(tm.load_mesh(path/'bore_fit_coupon.stl')),2)
            for i,bed in enumerate(d['printer_bed']):
                self.assertLess(manifest['print_plate_bounds_mm'][1][i],bed)
            saved=json.loads((path/'manifest.json').read_text())
            self.assertEqual(saved['geometry_id'],manifest['geometry_id'])
        for change in ({'bore_clearance':-1},{'pilot_diameter':4},{'bolt_x':3},{'contact_z':15}):
            with self.assertRaises(ValueError): holder_halves(dict(d,**change))
