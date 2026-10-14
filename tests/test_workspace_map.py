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
