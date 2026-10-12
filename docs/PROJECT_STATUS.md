# Project status and open design decisions

Last reviewed: 2026-10-12. Update this document when capabilities or physical evidence change. Source code describes behavior; a passing mocked test is not a lab commissioning result.

## Established project choices

- Native PySide6 desktop UI with emphasis on readable controls, diagrams and live feedback.
- macOS simulation/development; Windows lab deployment.
- Dobot **Magician Lite**, MagicBox over USB, three-finger pneumatic soft gripper. Software uses DobotLink and `dobotkit`; this is not the larger Magician arm.
- PalmSens **EmStat4S LR**, USB, Python SDK adapter. Fixed reference and counter electrodes; robot handles the working electrode.
- Nominal working-electrode rod diameter is 6 mm. A pickup holder and automatic electrical contact are being developed.
- Common experiment inputs stay on Experiment. Manufacturing settings belong on Rack design, separate from robot calibration.
- Normal release uses the relaxed **pump-off** state, based on the user's observation of the physical gripper. Powered full-open remains a manual action.
- Rectangular and radial racks share the same slot mapping for movement and exports. Demonstrations start small, with a goal of more than 20 electrodes.

## Implemented in software

- Simulation and lazy hardware adapters, explicit connection/homing, queued motion verification and live pose feedback.
- CV batches, original-slot return, dipping rinse, cancellation/failure records and partial measurement export.
- Robot-only rehearsal and a compact preset anchored to a freshly reported pose.
- Main-page plot/camera/queue; manual jog, absolute moves, teaching and three gripper commands.
- Persistent settings, inline geometric checks and pinned calibration/workspace diagrams.
- PDF placement templates, legacy socket rack and modular holder-supported rack exports.
- Modular rack: adjustable holder and interface dimensions, separate tops/feet/holders, fit coupon, bed-fit checks, quantities, geometry IDs and assembly origins/rotations.
- Unit tests, offscreen UI checks and a mocked hardware UI integration check. No cloud service is required to run the app.

## Physical evidence and assumptions

The user supplied working basic Dobot movement code and camera capture code, and reported the gripper's three pneumatic states. The full application hardware adapters and sequence have **not been reported as commissioned on the actual lab setup**.

Default station coordinates and workspace limits are placeholders. Robot feedback is tool pose, not successful pickup. There is no camera-based pickup detection, continuity sensor, force feedback, obstacle model or autonomous recovery.

The modular example uses an 18 mm body / 24 mm flange holder, 13 mm rod insertion and a 100 mm rod, leaving 87 mm hanging. Its physical seat is 97 mm above the bench for 10 mm tip clearance. Feet use provisional push fits and must be fixed to the bench. Holder retention, grip envelope, tall-foot stiffness, printing clearance and material compatibility remain untested.

**The modular holder/rack is not a validated cell assembly.** The nominal cell defaults are a 50 × 70 mm beaker and a different shoulder/tip geometry. An 87 mm hanging assembly cannot simply be assumed to fit that cell. Measure/adapt electrode length, cap seating, beaker geometry and liquid level before hardware use. Current validation does not establish the complete rack-to-cell physical assembly or collision clearance.

The `cad/gripper` probe bracket assumes a rigid mounting neck that has not been measured. All metal contacts, conductors, spring probes and retention hardware are separate purchased/assembled components. Neither the bracket nor pickup holder is electrically qualified.

## Decisions still needed

| Question | Evidence needed / next useful step |
| --- | --- |
| Holder grip fit | Actual collar/body size, three finger contact height and relaxed/closed envelopes; small fit trial |
| Rack stability and reuse | Print coupon/foot/top, test peg fit and wobble, choose bench fixing and material |
| Cell/holder compatibility | Actual glassware dimensions, rod/hanging length, cap seating and immersion geometry |
| Automatic WE connection | Choose holder conductor/pad, spring contact and cable route; measure continuity and retention |
| Electrical-contact workflow | Decide fixed cell contact versus gripper contact; a gripper contact likely needs hold-during-CV sequencing |
| Hardware commissioning | Verify connection, homing, release/close, measured poses, dummy route, SDK acquisition and stop behavior |
| Recovery and detection | Define detectable failure states before introducing camera-based retries or automatic motion recovery |
| Future electrode formats | Define flag-electrode holders/inserts and clearance envelopes; current printable holder is for rods |

## Evidence to retain from commissioning

Record date, software revision, physical device/SDK versions, measured fixture/tool dimensions, tested profile, dummy versus real electrode, observed results and unresolved issues. Use a dedicated dated document or a clearly labelled example profile; keep personal measurements and raw experimental data outside Git unless the user explicitly wants them included. Mark assumptions as measured only when evidence is provided.

On 2026-10-12, the user confirmed direct commits/pushes to `main` and requested migration to **public** [aalto-ema/electrobot](https://github.com/aalto-ema/electrobot). GitHub is now the primary repository, with the existing Git history preserved. The previous GitLab repository remains available; its remote is retained as `gitlab` in the migration checkout. The source had one branch (`main`) and no tags at migration. This migration covers Git content/history, not GitLab issues or service configuration. A later user preference can change the workflow. Do not infer additional completed hardware verification from the example CAD files.
