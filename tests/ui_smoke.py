import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from electrobot.app import Window,STYLE
app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
w=Window(); w.show(); app.processEvents()
assert w.read_settings().electrodes==3
for i in range(5):
    w.nav.setCurrentRow(i); app.processEvents()
    w.grab().save(str(Path('cad')/f'ui-{i}.png'))
w.nav.setCurrentRow(0)
w.fields['electrodes'].setValue(1); w.fields['simulation_speed'].setValue(100)
w.fields['cycles'].setValue(1); w.start_run()
deadline=time.monotonic()+10
while w.worker.isRunning() and time.monotonic()<deadline:
    app.processEvents(); time.sleep(.01)
app.processEvents()
assert not w.worker.isRunning(), 'Run did not complete'
assert w.progress.value()==1
assert w.state.text()=='Completed',w.state.text()
assert w.start.isEnabled()
assert len(w.plot.data[1])>0
w.grab().save('cad/ui-run.png')
w.fields['simulation_speed'].setValue(1); w.start_run(); w.pause_run()
assert w.paused
w.stop_run(); deadline=time.monotonic()+3
while w.worker.isRunning() and time.monotonic()<deadline:
    app.processEvents(); time.sleep(.01)
app.processEvents(); assert not w.worker.isRunning(); assert w.state.text()=='Stopped'
w.close(); app.processEvents()
print('UI settings, all five pages, batch completion, live plot, stop while paused and thread shutdown passed')
