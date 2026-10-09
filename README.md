# Electrobot

PySide6 desktop prototype for a Dobot Magician Lite + MagicBox and PalmSens EmStat4S LR electrochemistry platform. Runs on macOS and Windows. Robot and potentiostat operations currently run **only in simulation**. Camera capture is real and optional.

## Start

Python 3.11+ recommended. From this folder:

```sh
python -m venv .venv
# macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_app.py
```

After setup, double-click **Start Electrobot.command** on macOS or **Start Electrobot.bat** on Windows. Both use the project’s `.venv` automatically, with no activation needed. You can also run `python run_app.py` from a terminal; it prefers `.venv` when present.

The dashboard runs a batch, overlays synthetic CV curves, pauses/resumes and stops. Experiment, cell/carrier and robot/rack pages provide editable settings with validation. Save persists `settings.json`; load accepts saved configurations. Each batch produces settings, event log, status summary and per-electrode CSVs in `runs/`. Stops retain partial data and record status; no recovery motion is simulated after stopping. Simulation timestamps represent protocol time; execution is accelerated by the configured multiplier.

Camera: connect with index -1 to search devices 0–4, or select a known index. Windows uses `CAP_DSHOW`, macOS `CAP_ANY`. Preview and PNG snapshots are available. Capture runs in its own thread. OS camera permission may be required. No image-based grasp detection is implemented yet.

## Initial defaults

- Three electrodes, five-column rack, 22 mm pitch.
- Rod Ø6 × 100 mm, Ø12 mm carrier shoulder, tip 50 mm below shoulder.
- Nominal 100 mL low-form beaker: Ø50 × 70 mm; assumed rim Ø53 mm **must be measured**.
- Cap: 4 mm plate, 6 mm outer skirt, 3 mm wall, 0.8 mm diametral rim clearance.
- WE bore Ø6.6 mm with Ø10 mm / 2 mm deep conical entrance; RE Ø8 mm and CE Ø6 mm openings at ±14 mm.
- Target immersion 15 mm. This requires a liquid surface 35 mm below the shoulder (31 mm below the plate underside). Volume alone does not fix immersion. Body/rim sizes vary, and the pouring spout must align with the cap notch.
- CV: 0 → +0.5 → −0.5 → +0.5 → −0.5 → 0 V, two cycles, 100 mV/s, 5 mV steps, 100 µA range, 2 s settling. These are **simulation examples**, not a validated electrochemical method. Reference label and all protocol parameters are editable.
- Three rinse dips, 1 s dwell each. Motion coordinates are arbitrary simulation placeholders; no hardware calibration is implied.

## Cap concept

`cad/cell_cap.stl` is a closed solid in mm; `cad/cell_cap.scad` is editable OpenSCAD. Export updated files from Cell & carrier or run `python -m electrobot.cad`. Top-view concept sketch is included as `cad/cap_sketch.svg`.

The removable cap has a surrounding locating skirt and an open spout notch/vent. The carrier shoulder rests on the plate; the tapered WE entrance guides insertion. RE/CE openings do **not** clamp electrodes: add compatible collars or clamps after their actual dimensions are known. Dry electrical contacts and a custom gripper are not included. It is a fit prototype, not a finalized cell fixture. Measure rim/body/spout and electrode lengths before printing. Print with the flat upper face on the bed and skirt upward, using a small fit coupon first if possible. Choose polymer/contact materials for the actual electrolyte and temperature; FDM parts may contaminate sensitive measurements. Keep the cap vented and fix the beaker externally so insertion cannot shift it.

## Hardware integration next

1. Record installed `dobotkit` version and verify gripper API against that version. Test opening/closing unloaded. The supplied movement example is the initial reference; no unverified actuator calls are used.
2. Teach and validate rack, cell, rinse and clearance coordinates in the lab. Robot base origin, tool offsets, workspace boundaries, seating/contact detection and collision clearance need calibration. There is no automated hardware mode yet.
3. Implement a Dobot driver and a PalmSens driver behind the experiment sequence. Verify device-specific stop, cell disconnect, completion and failure behaviour. UI Stop is currently a simulation control, not an emergency stop.
4. Commission dry contacts and shoulder seating. Add pickup detection and bounded retries only after a reliable detection method is tested.

The architecture currently contains a reusable experiment engine, simulated robot/potentiostat, a Qt run worker and independent camera worker. Later hardware adapters should expose the same operations but also provide completion/error feedback rather than assuming success.

## Verification

```sh
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python tests/ui_smoke.py
```

Sources: [PalmSens EmStat4S specifications](https://assets.palmsens.com/product/emstat4s/), [PalmSens Python measurement documentation](https://sdk.palmsens.com/python/latest/_attachments/measuring/index.html), [Dobot Python library repository](https://github.com/mslopgk/dobotkit), [Qt thread signals](https://doc.qt.io/qtforpython-6.11/examples/example_widgets_thread_signals.html), [OpenCV VideoCapture](https://docs.opencv.org/4.5.5/d8/dfe/classcv_1_1VideoCapture.html). Beaker body dimensions are nominal placeholders; actual glassware must be measured.
