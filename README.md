# Electrobot

PySide6 desktop workbench for a Dobot Magician Lite + MagicBox and PalmSens EmStat4S LR electrochemistry platform. Choose **Simulation** for development on macOS or **Hardware** for lab commissioning. The real drivers are implemented against `dobotkit 0.2.0` and `pypalmsens 2.2.0`; they have been tested with device doubles, not yet on the physical lab setup.

![Experiment workspace](cad/ui-run.png)

## Install and start

Python 3.11–3.14. From the project folder:

```sh
python -m venv .venv
# macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_app.py
```

Double-click **Start Electrobot.command** on macOS or **Start Electrobot.bat** on Windows after setup. The launchers use `.venv` automatically. Simulation does not import the hardware SDKs or require .NET.

For hardware, additionally install:

```sh
python -m pip install -r requirements-hardware.txt
```

On the Windows lab computer:

- Install the **.NET Desktop Runtime 10.0** matching your Python architecture. The packaged PalmSens Windows runtime configuration requires both `Microsoft.NETCore.App` and `Microsoft.WindowsDesktop.App` 10.0.
- Install the PalmSens USB drivers; PSTrace normally supplies these. Close PSTrace before connecting from Electrobot.
- Start **DobotLink**. `dobotkit` talks to its WebSocket service (default `localhost:9090`); DobotLink relays commands over USB/COM to the arm. Set the correct arm COM port in Settings, or use `auto` when exactly one Dobot is available.
- Connect the camera and allow OS camera access. Windows capture uses DirectShow; macOS uses the default OpenCV backend.

## Experiment workspace

Live robot tracking appears above the electrode queue on Experiment and beside the controls on Manual robot. Orange markers show current tool position in XY and XZ views; grey lines show recent reported motion, and C/R mark cell/rinse. The diagrams auto-fit the stations and recent positions. XYZ/R values distinguish hardware feedback from simulated positions. Calibration and Workspace diagrams also show the current pose. Hardware moves publish pose feedback during queue execution (about 10 Hz subject to RPC latency), with idle polling every 0.5 s. Simulation interpolates positions. Missing idle feedback or disconnect clears the marker. Tracking reflects reported tool pose, not a camera-verified electrode position or a collision check.

**Robot rehearsal** runs the same pickup → seat/release in cell → retrieve → rinse → return sequence without CV or a required potentiostat connection. It actively opens/closes the gripper, so it can be used with an empty rack for a movement check or with dummy carriers to test handling. Use one electrode initially. The configured settling time is the brief stand-in wait at the cell; CV duration is omitted. Rinse settings and robot speed still apply. Hardware requires connection, explicit homing and verified calibration/fixture flags just like a batch. Stop remains available. The rehearsal follows the current release-in-cell workflow, not the future hold-during-CV design.

For a robot-only rehearsal, disconnect the WE lead from an independently controlled potentiostat. An app-connected potentiostat is commanded cell-off before movement and during cleanup, but is never asked to measure. Rehearsals save settings, events and a summary marked `robot_rehearsal`; they create no electrochemistry CSV or synthetic CV data.

The main page includes batch name, first rack slot, number of electrodes, CV cycle count, start/end and vertex potentials, scan rate, settling time, and rinse settings. It also contains device connection status, start/stop controls, per-electrode progress, a CV plot, a compact camera preview with snapshots, and the activity log. The lower workspace has three resizable columns: a compact CV plot, camera/activity, and the electrode queue on the right. Drag the dividers to adjust their widths.

The camera is independent of robot/potentiostat mode: a real camera can be used during a simulated batch. No pickup detection or camera-based recovery is implemented yet.

The plot overlays electrodes or shows a selected electrode. Displayed points are decimated for long batches so the UI remains responsive; CSV exports retain every received sample. Pause/resume is available in simulation. Hardware pause is disabled because interrupting a CV sweep would change the experiment; use Stop to abort.

Native PalmSens CV returns to its start potential, so the UI has a combined **Start / end** setting. The simulator follows that same protocol. The reference label, potential step, fixed current range, mains frequency and simulation multiplier live under Settings → Measurement defaults.

## Manual robot

Use **Manual robot** to read the reported pose, home, jog XYZ/R, move to an absolute target, and open/close the gripper. Commands run in the same serialized worker as experiments, so batch and manual operations cannot compete for a device. Operations and mode changes are disabled during an active command.

Hardware connection does not home, move, or actuate the gripper. Homing is explicit and required before hardware motion. Moves use `MOVL_XYZ`, wait for queued-command completion, and then verify reported XYZ/R against the configured tolerance. Timeouts, cancellation and pose mismatch stop and clear the queue. Rehome before subsequent hardware movement after a stop.

**Teach station** copies the reported pose into rack slot 1, cell seating, rinse dipping, or travel height settings. Teaching and changes to station/workspace coordinates clear the calibration flag. Save the configuration after verifying the route. Gripper state is the *commanded* state, not confirmation of a successful pickup.

## Settings and lab commissioning

Settings groups persistent design and calibration parameters into Devices, Measurement defaults, Robot calibration, Workspace, and Cell & carrier tabs. Configurations save to `settings.json` and can be loaded from JSON. Profiles never connect hardware or change the selected mode automatically; every app session starts in Simulation.

Robot calibration includes **Compact rehearsal from current pose**. With an idle connected robot (homed in hardware mode and commanded open), this reads a fresh pose without motion and anchors rack slot 1 to it. Cell is +10 mm X, rinse is +10 mm X/+10 mm Y, and travel Z is +5 mm; tool R is preserved. It selects one electrode, one 0.5 s rinse dip, 1 s settling and velocity/acceleration settings of 10. Calibration and fixture readiness are cleared. An incompatible preset is rejected without changing any settings; move manually to a verified clear intermediate pose and try again. Use only with an empty gripper initially.

Robot calibration and Workspace use the same top/side diagram, including X/Y/Z bounds, radial limits and the live robot position. These diagrams explain rack coordinates and slot ordering, pitch, station approach heights, travel Z, vertical-axis rotation and the intersection of Cartesian bounds with the radial band. Rack columns and rows through the last selected slot update dynamically; filled dots mark selected electrodes. Rack, cell and rinse XY points, station Z heights, travel height, workspace rectangle and radial band are plotted from actual coordinates. Equal XY scaling preserves relative distances; station columns in the side view are categorical. Labels and points update as settings change. The diagrams do not model collisions. Tooltips and motion notes explain tolerances, timeouts and dwell settings. Both tabs show live incompatibility messages and highlight related fields. Checks cover height ordering, rack pitch, inverted bounds and all selected station/transfer endpoints, in simulation as well as hardware. Invalid settings disable experiment and rehearsal starts. Passing these checks does not establish physical clearance.

A suggested first lab session:

1. Select Hardware, set the Dobot COM port and PalmSens device ID if more than one instrument is present, and connect the robot. Connect the potentiostat independently. An ambiguous discovery result is an error; the app does not silently pick a device or fall back to simulation.
2. Clear the homing path and use Manual robot → Home. Test the gripper unloaded. The hardware driver uses `arm.effector.grip(on, queued=False)`; `True` closes it and `False` opens it. Check this behaviour on your installed gripper.
3. Jog in small increments and teach rack slot 1, cell and rinse poses. Configure rack spacing/columns, tool rotation, travel height, and endpoint workspace bounds. Validate all straight-line approaches and clearance transfers, including the initial lift from the current pose.
4. Verify carrier seating, immersion, release/retrieval, gripper clearance and dry WE electrical contact. Mark **Station poses and paths calibrated** and **Gripper, seating and dry contact verified**. Geometry changes clear the fixture flag.
5. Connect the potentiostat, select a chemistry-appropriate CV protocol and current range, and start with one electrode. The device validates the method before any batch movement.

A hardware batch turns the cell off before handling the electrode, lifts vertically at the current station before transferring at travel height, inserts/releases the carrier, waits for settling, runs CV, turns the cell off, retrieves, dips in the rinse beaker, and returns to the exact original rack slot. If measurement or movement fails, it stops and records the failure; it does not automatically attempt recovery.

**Stop is a software command, not a physical emergency stop.** Robot stopping is limited by the DobotLink RPC response time and controller behaviour. Workspace limits constrain endpoints; they do not model obstacles, joint limits or collision-free paths. Use the hardware emergency-stop facility when needed. The defaults are simulation placeholders and must be calibrated.

The pneumatic gripper pump is turned off by device disconnection. After a stop, secure any held electrode and open the gripper before disconnecting or closing. The UI blocks disconnect/close while the hardware gripper is commanded closed; closing during a hardware operation first requests a stop and leaves the app available for recovery.

## Data and failure records

Every batch creates a unique folder under `runs/` with the configuration snapshot, `events.json`, `summary.json`, and per-electrode CSVs. Hardware acquisition also saves the SDK JSON Lines stream. CSV current is normalized to µA and potential to V; unsupported units fail the measurement rather than being mislabelled. CSV time is **nominal CV sample time** (`step / scan_rate`), since CV callbacks provide E/I rather than measured timestamps; `time_source` makes this explicit. Simulation uses protocol timestamps. `synthetic` identifies simulated versus measured values.

CSV rows are flushed as they arrive. Partial measurements survive cancellation and are marked stopped/failed. Failed cell-off or robot-stop cleanup is recorded explicitly. No retrieval or rinse proceeds after measurement failure. Summary grip state represents commands, not detected electrode presence.

## Initial defaults and cap concept

- Three electrodes, five-column rack, 22 mm pitch.
- Rod Ø6 × 100 mm, Ø12 mm carrier shoulder, tip 50 mm below shoulder.
- Nominal 100 mL low-form beaker: Ø50 × 70 mm; assumed rim Ø53 mm **must be measured**.
- Cap: 4 mm plate, 6 mm outer skirt, 3 mm wall, 0.8 mm diametral rim clearance.
- WE bore Ø6.6 mm, Ø10 mm / 2 mm deep conical guide; RE Ø8 and CE Ø6 openings at ±14 mm.
- Target immersion 15 mm requires liquid 35 mm below the shoulder (31 mm below plate underside). Volume alone does not fix immersion.
- CV: 0 → +0.5 → −0.5 → +0.5 → −0.5 → 0 V, two cycles, 100 mV/s, 5 mV step, 100 µA range; 2 s settling; three rinse dips at 1 s per dip. These are simulation examples, not a validated electrochemical method.

`cad/cell_cap.stl` is a closed solid in mm; `cad/cell_cap.scad` is editable OpenSCAD. Export updated geometry from Settings → Cell & carrier or run `python -m electrobot.cad`. `cad/cap_sketch.svg` shows the concept.

The cap has a surrounding locating skirt and open spout notch/vent. The carrier shoulder rests on the plate; the tapered opening guides the WE. RE/CE openings need separate compatible collars/clamps. The cap model does not include electrical contacts or gripper parts. Measure glassware and electrode lengths before printing. Print flat upper face on the bed, skirt upward. Choose materials for the actual electrolyte and temperature; FDM parts can contaminate sensitive measurements. Keep the cap vented and fix the beaker externally.

Provisional pickup-collar and three-finger probe-bracket STLs are in [`cad/gripper`](cad/gripper/README.md), with editable JSON dimensions and a Python generator. Their mounting geometry has not been fitted to the physical gripper. The measurement checklist, print notes and separate metal components are documented there. The provisional 24 mm flange also requires a larger rack pitch than the current 22 mm default. This design requires a hold-during-CV sequence, which is not yet implemented.

## Placement guide and printable racks

Settings → **Export placement PDF** creates an A4 landscape overview, a complete station/slot coordinate checklist, and tiled **1:1 placement templates**. Print at 100% / Actual size and verify each 50 mm scale line. Trim at tile frames and assemble with tile row increasing along +Y. The guide marks the robot's XY datum and directions, not an unmeasured physical base footprint. Beaker outlines use the entered cell and rinse diameters and assume the cell WE axis is central. Z values are robot tool positions, not heights inferred from the printed rack or bench. Physical clearances and actual tool offsets still require calibration. Export uses Qt's PDF writer, so there is no additional Python dependency.

Settings → Robot calibration → **Rack layout** selects rectangular or radial geometry. In radial mode, First row radius and Slot 1 angle are measured about the robot XY origin; positive angles turn from +X toward +Y. Columns means slots per arc row, Angle between slots gives angular spacing, and Slot pitch gives the radial spacing between rows. First-slot X/Y are ignored. Teaching the first rack slot updates radius/angle/Z in radial mode. The compact rehearsal preset returns to rectangular layout. Slot mapping is shared by movement, diagrams, PDF and CAD. Calibration checks include socket/carrier separation; a full row spanning 360 degrees is rejected. Radial racks do not imply collision-free transfers between slots.

**Export rod rack STL + OpenSCAD** creates a connected base with blind upright sockets, plus a manifest that maps local printable coordinates back to robot coordinates. It prints complete rows through the last selected slot, including inactive end-of-row sockets. Change the electrode count/first slot to change rack extent. Socket diameter follows rod diameter plus printing clearance; depth, wall, post height, base thickness and edge margin are adjustable. The first design assumes a carrier shoulder resting on the socket lip, with the active tip suspended above the blind floor. Test with dummy carriers and verify actual seating; a bare rod without a shoulder may rest on its tip. Flag electrodes are not supported yet. Changing rack geometry clears fixture readiness. **Teach gripping Z after assembling the rack**: its tool Z does not determine printable rack height.

The [`cad/radial-example`](cad/radial-example) folder contains a 24-slot, three-row prototype, editable settings, STL, OpenSCAD, manifest and printable guide. Its footprint is approximately **95 × 253 mm**, height **69 mm**; check printer-bed size before slicing. Future larger racks may require modular sections. These are uncommissioned example positions and dimensions, not a lab-ready calibration.

## Verification

```sh
python -m unittest discover -s tests -v
# macOS / Linux
QT_QPA_PLATFORM=offscreen python tests/ui_smoke.py
QT_QPA_PLATFORM=offscreen python tests/hardware_ui_smoke.py
# Windows PowerShell
# $env:QT_QPA_PLATFORM='offscreen'; python tests/ui_smoke.py
```

Tests cover sequence/data retention, SDK parameter/unit mapping, abort/cell-off, robot completion/tolerance/cancellation, selection ambiguity, hardware preflight, camera search/disconnection, and cap mesh validity. An additional hardware UI smoke run uses the real adapters with mock devices. UI smoke checks cover the workspace, manual control and teaching, settings persistence, mode isolation, pause/stop and shutdown. Hardware behaviour still needs physical commissioning.

Sources: [Dobot library API/source](https://github.com/mslopgk/dobotkit), [PalmSens Python SDK installation](https://dev.palmsens.com/python/latest/_attachments/installation/), [PalmSens CV](https://sdk.palmsens.com/python/latest/_attachments/reference/methods/cyclic_voltammetry/), [PalmSens instrument management](https://sdk.palmsens.com/python/latest/_attachments/reference/instrument_async/), [EmStat4S specifications](https://assets.palmsens.com/product/emstat4s/), [OpenCV VideoCapture](https://docs.opencv.org/4.5.5/d8/dfe/classcv_1_1VideoCapture.html).
