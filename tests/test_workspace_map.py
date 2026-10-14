import unittest
from electrobot.workspace_map import axis_values,scan_axes,scan_points,validate_saved_map


class WorkspaceMapTests(unittest.TestCase):
    def spec(self):
        return dict(x_min=190,x_max=210,x_step=10,y_min=0,y_max=0,y_step=10,
                    z_min=50,z_max=100,z_step=25,r=0)

    def test_grid_includes_endpoints_and_vertical_columns(self):
        self.assertEqual(axis_values(0,25,10),[0,10,20,25])
        points=scan_points(self.spec())
        self.assertEqual(len(points),9)
        self.assertEqual(points[:3],[(190,0,50,0),(190,0,75,0),(190,0,100,0)])
        for changes in (dict(x_step=0),dict(r=91),dict(x_step=.01),dict(z_min=101)):
            with self.assertRaises(ValueError): scan_axes(dict(self.spec(),**changes))

    def test_saved_maps_preserve_unknown_and_reject_false_completeness(self):
        data=dict(format='electrobot-controller-workspace-v1',source='DobotLink.CheckPoseLimit',
                  spec=self.spec(),points=[[190,0,50,0,True,False]],complete=False)
        self.assertEqual(len(validate_saved_map(data)['points']),1)
        with self.assertRaises(ValueError): validate_saved_map(dict(data,complete=True))
        with self.assertRaises(ValueError): validate_saved_map(dict(data,points=data['points']*2))
        with self.assertRaises(ValueError): validate_saved_map(dict(data,points=[[190,0,50,0,1,False]]))

    def map(self):
        spec=dict(x_min=150,x_max=250,x_step=25,y_min=-50,y_max=50,y_step=25,
                  z_min=-20,z_max=80,z_step=25,r=0)
        return dict(format='electrobot-controller-workspace-v1',source='DobotLink.CheckPoseLimit',
                    spec=spec,points=[[*p,True,True] for p in scan_points(spec)],complete=True)

    def test_envelope_rectangle_missing_rejected_and_rotation(self):
        from electrobot.workspace_map import Envelope
        data=self.map(); env=Envelope(data)
        self.assertEqual(env.rectangle(0,60,0),(150,250,-50,50))
        self.assertIs(env.status(162,-12,0,60,0),True)
        self.assertIsNone(env.status(162,-12,-30,60,0))
        self.assertIsNone(env.status(162,-12,0,60,10))
        data['complete']=False
        data['points']=[p for p in data['points'] if p[:3]!=[150,-25,30]]
        self.assertIsNone(Envelope(data).status(162,-12,0,60,0))
        data['points'].append([150,-25,30,0,False,True])
        self.assertIs(Envelope(data).status(162,-12,0,60,0),False)

    def test_rectangle_does_not_bridge_hole_and_fit_preserves_layout(self):
        from electrobot.workspace_map import Envelope,fit_rack
        from electrobot.config import Settings
        from dataclasses import asdict
        import json
        data=self.map()
        for p in data['points']:
            if p[0]==200: p[4]=False
        bounds=Envelope(data).rectangle(0,60,0)
        self.assertTrue(bounds[1]<=175 or bounds[0]>=225)
        for layout in ('rectangular','radial'):
            s=Settings(workspace_map=self.map(),rack_layout=layout,electrodes=3,rack_columns=3,
                       rack_x=280,rack_y=80,rack_radius=280,rack_start_angle=30,
                       rack_angle_step=10,rack_z=0,cell_z=0,rinse_z=0,safe_z=60)
            proposed=fit_rack(s,s.workspace_map)
            self.assertEqual(proposed.rack_pitch,s.rack_pitch)
            self.assertEqual(proposed.rack_columns,s.rack_columns)
            for pose in proposed.rack_export_positions():
                self.assertIs(Envelope(s.workspace_map).status(*pose[:2],0,60,0),True)
            self.assertEqual(Settings(**json.loads(json.dumps(asdict(proposed)))).workspace_map,s.workspace_map)
