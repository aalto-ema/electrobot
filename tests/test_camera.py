import unittest
from unittest.mock import patch
import numpy as np
from electrobot.camera import CameraWorker

class CameraTests(unittest.TestCase):
    def test_search_release_and_disconnect(self):
        import cv2
        class Capture:
            def __init__(self,opened): self.opened=opened; self.released=False; self.reads=0
            def isOpened(self): return self.opened
            def read(self):
                self.reads+=1
                return (True,np.zeros((4,6,3),dtype=np.uint8)) if self.reads<3 else (False,None)
            def release(self): self.released=True
        missing=Capture(False); working=Capture(True); frames=[]; states=[]
        worker=CameraWorker(-1); worker.frame.connect(frames.append); worker.status.connect(states.append)
        with patch.object(cv2,'VideoCapture',side_effect=[missing,working]) as factory:
            worker.run()
        self.assertEqual(factory.call_count,2); self.assertTrue(missing.released); self.assertTrue(working.released)
        self.assertEqual(len(frames),1); self.assertEqual(frames[0].width(),6)
        self.assertIn('Camera disconnected',states)

if __name__=='__main__': unittest.main()
