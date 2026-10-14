# Architecture and change map

This document maps implementation responsibilities. User setup and operation belong in the [README](../README.md); current physical assumptions belong in [Project status](PROJECT_STATUS.md).

## Runtime

`run_app.py` selects the project virtual environment when present, changes to the repository root and starts the native Qt application. The Windows/macOS launchers call it. `electrobot/__main__.py` is an alternative entry point.

| Module | Responsibility |
| --- | --- |
| `app.py` | Main window, Experiment/Manual robot/Settings pages, parameter widgets, command submission, feedback and export actions |
| `config.py` | Settings defaults and validation, rectangular/radial slot coordinates, complete-row export extent, protocol points |
| `worker.py` | Serialized device owner, mode/connection state, idle pose polling, command execution and Qt signals |
| `engine.py` | Experiment/rehearsal sequencing, cancellable waits, simulation adapters and run output |
| `drivers.py` | Lazy Dobot/PalmSens adapters, queue/pose checks, SDK method mapping, units and cleanup |
| `camera.py` | Independent OpenCV capture worker and camera discovery |
| `widgets.py` | Shared styling, controls, CV plot, camera preview and cap sketch |
| `calibration_widgets.py` | Coordinate diagrams and live XY/XZ robot trackers |
| `rack_widgets.py` | Holder-seat section and modular rack schematic |

GUI actions submit a settings snapshot and payload to `DeviceWorker`. Signals publish pose, device state, events, measurement points and completion to the GUI. Experiment and manual commands share the same queue; they cannot operate hardware concurrently. The camera is independent of Simulation/Hardware mode.

Normal experiments release the carrier in the cell before measurement, retrieve it afterward, dip it in rinse water, then return it to its original slot. Rehearsal follows the handling route and skips measurement. A future gripper-mounted electrical contact may require a different hold-during-measurement workflow; that workflow is not implemented.

## Settings and coordinate contract

`Settings` fields persist as JSON. New fields need defaults to load older profiles. The application reads/writes fields generically; construction and enum choices still need explicit UI widgets. Profiles preserve the selected session mode; a new session starts in Simulation.

`rack_pose(index)` maps a one-based slot to tool XYZ. Rectangular rows advance in +X, then +Y. Radial rows advance in angle, then radius; positive angles turn +X toward +Y. `rack_export_positions()` includes complete rows through the final selected slot, capped at 100. Batch motion uses selected slots; diagrams/CAD also show spare slots in the completed final row.

Station/transfer settings use reported tool Z. CAD uses physical bench height and print-local coordinates. A manifest records how print-local XY maps back to robot XY; modular tops additionally require rotation. Teaching actual tool Z remains a commissioning step.

Geometry changes clear relevant readiness flags. `calibration_issues()` feeds inline messages, field highlights and start eligibility. `validate()` checks broader parameter consistency, and `validate_batch()` adds hardware readiness/pose checks. Extending settings should keep these layers coherent.

## CAD and exports

| Module/source | Output |
| --- | --- |
| `cad.py` | Parametric cell-cap STL and OpenSCAD |
| `rack_cad.py` | Rack export dispatcher, legacy socket rack and shared footprint |
| `lattice_rack.py` | Modular top supports, identical fork feet, pickup holder, fit coupon, quantities and assembly manifest |
| `mesh_utils.py` | Connected-solid check without introducing SciPy |
| `placement_pdf.py` | Qt PDF overview, coordinate checklist and actual-size placement tiles |
| `cad/gripper/generate.py` + `dimensions.json` | Provisional collar and separate electrical-probe bracket parts |
| `cad/modular-example/generate.py` + `example-config.json` | Reproducible modular rack files and mesh-based assembly preview |
| `cad/three-electrode-print/generate.py` | Single-STL compact three-seat kit using production CAD, clustered feet, two fit coupons and plate manifest/preview |

CAD uses Shapely outlines, trimesh extrusion/meshes and Manifold booleans. Each exported part is checked for closed volume and one connected solid. Top modules are grouped per rack row and limited by slots/module. Geometry is normalized to local coordinates so identical rotated shapes share an STL and quantity. Each module records its world origin, rotation, slot coordinates and foot centres.

Fork feet have two columns, insertion pegs and a bench-fixing tab. Their local axis/position must be transformed using the module rotation. Tops are independent; there are no inter-module joining clips. Compatibility depends on interface dimensions and, for feet, height. Do not identify reusable parts only by filename; consult geometry IDs.

## Verification and useful changes

Run `python scripts/check_project.py`; see its `--help` for the short unit-only option. This runs the existing test commands, does not install dependencies, and never connects physical devices. UI checks isolate settings and run output but refresh screenshot artifacts in `cad/`.

| Change | Usually inspect/update |
| --- | --- |
| Settings field | `config.py`, UI field/readiness wiring, persistence checks, diagrams/export consumers |
| Robot/gripper behavior | Simulation and hardware adapters, worker command/state, engine sequence, driver tests, UI checks |
| Measurement protocol/data | Settings points, PalmSens mapping, simulation, streaming/export tests, documented units/time source |
| Rack mapping/layout | Shared Settings mapping, calibration checks, diagrams, CAD/PDF and mapping tests |
| Manufacturing geometry | Generator, dimensional/interface tests, example config/manifests/STLs and preview/assembly notes |
| UI layout | `app.py`/widgets, normal and compact screenshots, offscreen UI checks |

Keep production hardware dependencies optional. `requirements.txt` supplies simulation/UI/CAD; `requirements-hardware.txt` adds pinned adapters. `requirements-lock.txt` is a recorded environment snapshot, not a substitute for maintaining the cross-platform runtime requirements.

## Repository workflow

The primary repository is public [aalto-ema/electrobot](https://github.com/aalto-ema/electrobot), migrated from Aalto GitLab on 2026-10-12 with Git history preserved. `origin` points to GitHub; the migration checkout retains the former remote as `gitlab`. New GitHub clones normally have only `origin`. Checked changes are committed and pushed directly to `main`, as the user confirmed. The README has clone and existing-checkout migration commands. Local calibration, run data and untracked files are not part of the Git-history migration.
