# Working on Electrobot

## Start here

- Read this file, `README.md`, and the relevant parts of `docs/ARCHITECTURE.md` and `docs/PROJECT_STATUS.md` before changing behavior.
- Inspect `git status` first. Preserve the user's work, local calibration profiles, and measurement data.
- This is a **PySide6 desktop application**, developed in macOS simulation and deployed to a Windows lab computer. Keep that workflow working; do not replace it with a web UI.
- User intent and authorization in the current conversation take precedence over this guidance. Complete authorized work without repeatedly asking for confirmation. Ask about consequential unknown requirements; routine implementation choices are yours to resolve.

## Project conventions

- Use English for code, UI and documentation unless the user requests otherwise. Record new user preferences here when confirmed.
- Keep common experiment controls on Experiment. Put persistent device, geometry and manufacturing parameters in Settings, with manual operations on Manual robot.
- Prefer native Qt controls and diagrams. Show dimensional relationships, live feedback and actionable validation near the relevant settings. Keep diagrams visible while parameters scroll.
- Keep dependencies modest. Reuse Qt for PDF/diagrams and the existing CAD libraries before adding packages. Hardware SDK imports remain lazy and optional in simulation.
- Use cross-platform `pathlib` paths and the active project virtual environment. Do not embed a developer's absolute paths or local COM port in source.
- Follow nearby code conventions. Avoid unrelated formatting changes or introducing a framework for a small feature.

## Behavioral constraints

- All robot and potentiostat calls belong to `DeviceWorker`, serialized on its thread. Camera capture has its own worker. Never block Qt's GUI thread with motion, measurement, capture or device polling.
- Start every application session in Simulation. Loading a profile must not connect devices, select Hardware or command motion. Hardware failure must not silently fall back to simulation.
- Connection must not home or actuate the gripper. Homing remains explicit; a stopped hardware robot requires rehoming before motion.
- **Normal gripper release is pump off:** `grip(False, enable=False, queued=False)`. Closing uses `True, enable=True`. Powered full-open is an explicit manual action. Display commanded grip state, not claimed pickup detection.
- Preserve stop/cancellation, queue completion and pose verification, cell-off cleanup, held-electrode disconnect guards, and partial-data retention. Do not add automatic recovery movement without defining the recovery behavior with the user.
- A rehearsal must never measure or create electrochemistry CSV data. It may operate an explicitly connected potentiostat only to turn its cell off.
- Do not use physical hardware as a software test. Hardware operation needs authorization for the operation; continue relevant work within an already authorized commissioning session without repeated permission requests.
- Configured workspace bounds are distinct from controller reachability checks. The latter query supported firmware limits at sampled path poses; neither establishes obstacle, whole-path or joint-limit clearance between samples. Never describe them as collision detection or a hardware safety certification.

## Settings, coordinates and data

- `Settings` is the source of truth. Add backwards-compatible defaults for new fields; connect UI read/apply, validation and readiness invalidation as appropriate.
- Use `Settings.rack_pose()` and `rack_export_positions()` for movement, diagrams, CAD and placement guides. Do not create a second slot-mapping formula in the UI or exports.
- Lengths are mm; tool R and rack angles are degrees; voltages are V; exported current is µA. Distinguish measured hardware data from synthetic data.
- Robot Z is the reported tool coordinate. Printed seat height and electrode tip depth are different physical quantities; do not infer or overwrite taught Z from CAD.
- Record data units and time source accurately. Hardware CV time is currently nominal step time, not a measured timestamp. Keep run configuration snapshots and failure records interpretable.
- `settings.json` and `runs/` are local, ignored files. Do not commit personal calibration or measurement output. Only commit clearly labelled examples under `profiles/` or `cad/`.

## CAD and physical assumptions

- Keep provisional dimensions explicit. Software tests and watertight meshes do not establish physical fit, grip retention, electrical continuity or material compatibility.
- Export closed, connected STL solids in mm and check intended print orientation, component dimensions and configured XY bed fit. Include a manifest and assembly notes for multi-part designs.
- Modular racks must preserve the coordinate mapping, part quantities, assembly origins/rotations, and reproducible geometry IDs. Reuse is conditional on compatible geometry and interfaces; do not promise arbitrary layouts share parts.
- Keep the electrode tip suspended clear of the rack. Hanging length must account for rod insertion and any additional active-tip projection.
- Printed holders do not include the metal contact pad, conductor, spring probe, bolts or rod-retention hardware. A pilot hole is not a printed thread.
- Update CAD sources/configuration, generated examples, relevant manifests and instructions together. Do not manually patch an STL to change a parametric design.

## Verification and delivery

- Preferred command: `python scripts/check_project.py`. It uses `.venv` when available and runs unit tests plus both offscreen UI checks. `--unit-only` runs just the unit suite.
- Choose checks appropriate to the change. UI changes need a screenshot review at the normal window size and the compact size where relevant; CAD changes need mesh, dimension, assembly/interface and export checks. Documentation-only edits need link/command consistency checks, not a full test rerun.
- UI tests use temporary settings/output directories and mock hardware. They refresh tracked screenshots under `cad/`; inspect changed screenshots and avoid committing unrelated image churn.
- Run `git diff --check`, review the diff and check the worktree before delivery. Report what changed, what passed, and remaining physical assumptions.
- User-confirmed workflow (2026-10-12): commit and push completed, checked changes directly to `main` on `https://github.com/aalto-ema/electrobot.git` (`origin`). The repository is public by explicit user choice. The previous Aalto GitLab remote is retained locally as `gitlab` for reference; routine pushes target GitHub. A later user preference overrides this. Use `codex/` for newly created branches if a task calls for one. Do not rewrite history or remove others' changes.
- Maintain `docs/ARCHITECTURE.md` and `docs/PROJECT_STATUS.md` proactively when code changes or conversations supply relevant new information. Update Architecture for module responsibilities, interfaces, coordinate/data contracts and development workflows; update Project status for capabilities, confirmed decisions, requirements, commissioning evidence and unresolved questions. Include necessary updates in the same delivery without waiting for a separate documentation request.
- Keep these documents concise and current rather than copying conversation transcripts. Distinguish proposals, confirmed decisions and measured results; record dates/evidence where useful. Do not treat conversation assumptions as verified lab measurements. Update only the document affected, and leave both unchanged when nothing relevant has changed.
