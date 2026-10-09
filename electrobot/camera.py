import sys
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

class CameraWorker(QThread):
    frame=Signal(QImage)
    status=Signal(str)
    def __init__(self,index=-1):
        super().__init__(); self.index=index
    def run(self):
        camera=None
        try:
            import cv2
            backend=cv2.CAP_DSHOW if sys.platform=='win32' else cv2.CAP_ANY
            for index in (range(5) if self.index==-1 else [self.index]):
                if self.isInterruptionRequested(): return
                candidate=cv2.VideoCapture(index,backend)
                if candidate.isOpened():
                    ok,frame=candidate.read()
                    if ok:
                        camera=candidate; self.status.emit(f'Camera connected · device {index}'); break
                candidate.release()
            if camera is None:
                self.status.emit('No camera found. Check device index and OS camera permission.'); return
            while not self.isInterruptionRequested():
                ok,frame=camera.read()
                if not ok:
                    self.status.emit('Camera disconnected'); break
                rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                h,w,_=rgb.shape
                self.frame.emit(QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy())
                self.msleep(33)
        except Exception as exc: self.status.emit(f'Camera error: {exc}')
        finally:
            if camera is not None: camera.release()
