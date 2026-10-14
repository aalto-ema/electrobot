import json
from pathlib import Path
import unittest
import trimesh
from electrobot.mesh_utils import connected_solids


class PrintPlateTests(unittest.TestCase):
    def test_three_electrode_plate_contains_complete_separate_kit(self):
        folder=Path(__file__).resolve().parents[1]/'cad/three-electrode-print'
        plate=trimesh.load_mesh(folder/'three-electrode-rack-kit.stl')
        manifest=json.loads((folder/'plate-manifest.json').read_text())
        source=json.loads((folder/'parts/rack_manifest.json').read_text())
        self.assertTrue(plate.is_watertight and plate.is_volume)
        self.assertEqual(connected_solids(plate),9)
        self.assertEqual(sorted(p['label'] for p in manifest['parts']),['A','B','F1','F2','F3','H1','H2','H3','R'])
        self.assertEqual(source['holder_quantity'],3); self.assertEqual(source['foot_quantity'],3)
        self.assertEqual(len(source['slot_robot_xyz']),3)
        expected=0
        for file,quantity in (('rack_top_01.stl',1),('rack_foot.stl',3),('pickup_holder.stl',3),('rack_fit_coupon.stl',1),('rack_fit_coupon_loose.stl',1)):
            expected+=trimesh.load_mesh(folder/'parts'/file).volume*quantity
        self.assertAlmostEqual(plate.volume,expected,places=1)
        for i,part in enumerate(manifest['parts']):
            lo,hi=part['bounds_mm']; self.assertAlmostEqual(lo[2],0)
            for axis,bed in enumerate(manifest['bed_mm']):
                self.assertGreaterEqual(lo[axis],manifest['bed_edge_margin_min_mm'])
                self.assertLessEqual(hi[axis],bed-manifest['bed_edge_margin_min_mm'])
            for other in manifest['parts'][i+1:]:
                b0,b1=other['bounds_mm']
                distance=sum(max(0,lo[axis]-b1[axis],b0[axis]-hi[axis])**2 for axis in (0,1))**.5
                self.assertGreaterEqual(distance,manifest['minimum_part_gap_mm']-.001)
