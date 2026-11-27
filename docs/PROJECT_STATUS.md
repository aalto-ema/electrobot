# Project status and open design decisions

Last reviewed: 2026-11-27. Update this document when capabilities or physical evidence change. Source code describes behavior; a passing mocked test is not a lab commissioning result.

## Established project choices

- MIT license, selected by the user on 2026-10-13; full text in the repository-root `LICENSE`.
- Native PySide6 desktop UI with emphasis on readable controls, diagrams and live feedback.
- macOS simulation/development; Windows lab deployment.
- Dobot **Magician Lite**, MagicBox over USB, three-finger pneumatic soft gripper. Software uses DobotLink and `dobotkit`; this is not the larger Magician arm.
- PalmSens **EmStat4S LR**, USB, Python SDK adapter. Fixed reference and counter electrodes; robot handles the working electrode.
- Nominal working-electrode rod diameter is 6 mm; the user confirmed the initial body diameter as 6 mm on 2026-10-14. A pickup holder and automatic electrical contact are being developed.
- Common experiment inputs stay on Experiment. Manufacturing settings belong on Rack design, separate from robot calibration.
- Normal release uses the relaxed **pump-off** state, based on the user's observation of the physical gripper. Powered full-open remains a manual action.
- Rectangular and radial racks share the same slot mapping for movement and exports. Demonstrations start small, with a goal of more than 20 electrodes.

## Implemented in software

- Simulation and lazy hardware adapters, explicit connection/homing, queued motion verification and live pose feedback.
- CV batches, original-slot return, dipping rinse, cancellation/failure records and partial measurement export.
- Robot-only rehearsal and a compact preset anchored to a freshly reported pose.
- Non-moving controller reachability queries for configured handling routes and manual moves; sampled station/lift/transfer checks, runtime alarm monitoring, no-progress watchdog and persistent copyable target/actual/fault feedback. Firmware support is not yet verified on the lab controller; unsupported queries are reported explicitly.
- Main-page plot/camera/queue; manual jog, absolute moves, teaching and three gripper commands.
- Persistent settings, inline geometric checks and pinned calibration/workspace diagrams.
- PDF placement templates, legacy socket rack and modular holder-supported rack exports.
- Modular rack: adjustable holder and interface dimensions, separate tops/feet/holders, fit coupon, bed-fit checks, quantities, geometry IDs and assembly origins/rotations.
- Compact three-electrode print kit in `cad/three-electrode-print`: one STL with a three-seat radial top, three clustered feet, three holders and two fit coupons. The user specified a Creality Ender-3 V2 and Cura on 2026-10-14. The kit fits the nominal 220 × 220 × 250 mm volume and is arranged for Cura All at Once (layer-by-layer) printing; no printer-specific G-code or complete-object sequential clearances have been validated.
- Unit tests, offscreen UI checks and a mocked hardware UI integration check. No cloud service is required to run the app.

## Physical evidence and assumptions

On 2026-11-27, DobotLink 5.13.0 running from the mounted installer image on Apple Silicon macOS connected to the MagicBox USB serial port through the pinned dobotkit client. The explicit `cu.usbmodem…` port was needed because discovery also listed unrelated serial ports. Pose, alarm state and 32 free queue slots were read successfully, then the session disconnected. Alarm IDs 0 and 73 were already present. No motion or alarm clearing was tested, and alarm 100 was absent in this snapshot. The earlier Mac App Store build (5.5.13) returned error 122 opening the same device.

Electrobot’s Qt Connect robot and Disconnect buttons were also tested on this Mac with DobotLink 5.13.0. Automatic port selection chose the USB callout device and the GUI displayed live pose feedback with flags 0 and 73.

A follow-up live test on 2026-11-27 read the alarms immediately before and after each of two queries. Queue-space returned 32 and CheckPoseLimit rejected the current stationary pose. Flags 0 and 73 persisted throughout. Reproducing alarm 100 during the complete rehearsal still requires the failing layout and a controller ready for movement. The driver now avoids repeated speed settings, stationary waypoint commands and queue-capacity reads after the final upload. Physical timing remains unmeasured.

On 2026-11-26 the user reported controller alarm 100 (0x64), currently displayed as unmapped, after the transfer-motion options were introduced. The user clarified that a separate route check passed with simplification, but the check inside rehearsal raised the alarm; both options enabled also produced the error. The exact failing pose and physical firmware alarm meaning remain unknown. No causal link to queued transfers or workspace limits is established. A confirmed software gap was corrected: preflight previously read alarms only before route queries, allowing a query-time alarm to escape a successful check. Checks now also read alarms after shortcut compilation, queue-space probing and each route target, retain phase/last query/options, and refuse to publish shortcuts when an alarm is detected. This prevents false success but is not a confirmed fix for the underlying controller alarm. Next evidence: Manual robot → Diagnostic details → Copy diagnostic report, option states, and the alarm description shown by Dobot software. Leave continuous motion disabled while investigating; no automatic alarm clearing or recovery movement has been added.

The user supplied working basic Dobot movement code and camera capture code, reported the gripper's three pneumatic states, and has begun robot rehearsal with the application. On 2026-10-14 they reported a stopped move after setting Travel Z to 100 mm, with Manual robot showing X=200, Y=0, Z=68.80, R=0. This suggests the initial vertical lift may have failed before sideways travel, but the cause is not confirmed by controller alarm data. This single observation is not a measured reach envelope. Full robot/potentiostat commissioning remains incomplete.

Default station coordinates and workspace limits are placeholders. Robot feedback is tool pose, not successful pickup. The new controller-sampled preflight and alarm/stall handling have passed mocked tests, not this physical fault scenario. There is no camera-based pickup detection, continuity sensor, force feedback, obstacle model or autonomous recovery.

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
| Speed controls | The user reported slow rehearsal on 2026-10-14. Installed `dobotkit 0.2.0` applies the same settings to PTP ratios and Cartesian limits, potentially compounding low values; compact preset uses 10/10. Confirm controller units/achieved speeds and consider separating those controls. No measured speed or new motion behavior is established. |
| Recovery and detection | Define detectable failure states before introducing camera-based retries or automatic motion recovery |
| Future electrode formats | Define flag-electrode holders/inserts and clearance envelopes; current printable holder is for rods |

## Evidence to retain from commissioning

Record date, software revision, physical device/SDK versions, measured fixture/tool dimensions, tested profile, dummy versus real electrode, observed results and unresolved issues. Use a dedicated dated document or a clearly labelled example profile; keep personal measurements and raw experimental data outside Git unless the user explicitly wants them included. Mark assumptions as measured only when evidence is provided.

On 2026-10-12, the user confirmed direct commits/pushes to `main` and requested migration to **public** [aalto-ema/electrobot](https://github.com/aalto-ema/electrobot). GitHub is now the primary repository, with the existing Git history preserved. The previous GitLab repository remains available; its remote is retained as `gitlab` in the migration checkout. The source had one branch (`main`) and no tags at migration. This migration covers Git content/history, not GitLab issues or service configuration. A later user preference can change the workflow. Do not infer additional completed hardware verification from the example CAD files.

## Workspace planning update — 2026-10-14

Implemented a native Workspace explorer in Manual robot and Settings → Workspace, following the user's request to reduce trial-and-error fixture placement. It queries controller limits without motion over an adjustable XY/Z grid at fixed R, shows per-height acceptance and an intersection across sampled Z heights, and distinguishes configured bounds from controller results. Exact coordinates can be copied to manual target fields without motion. JSON/CSV exports and offline JSON inspection retain partial maps and unknown points.

Mocked checks cover height-dependent acceptance, unsupported firmware, cancellation preserving homing, no movement/gripper/queue commands, and manual-target copying. Normal and compact screenshots were reviewed. This is a controller-reported sample map, not a measured physical envelope; CheckPoseLimit support and accuracy on the user's firmware remain unverified.

## Initial electrode selection — 2026-10-14

The user selected the cylindrical electrodes shown in their ruler photograph for initial trials. The photo shows a black insulating body, an upper ring/shoulder-like feature and a protruding metallic terminal; exact model, body/flange dimensions, terminal diameter and exposed length remain unconfirmed. Do not infer precision CAD dimensions or connector compatibility from this image. Existing 100 mm rod/13 mm insertion print examples are provisional and have not been adapted to this electrode.

Proposed, not selected or validated: a split pickup carrier retained on the insulating body around the upper body, with a removable terminal socket wired to a dry external contact ring. A compliant contact fixed to the cell fixture would engage that ring when seated, preserving the current release-in-cell workflow and avoiding a robot cable. Mechanical seating must carry the load independently of the terminal/contact. A gripper-mounted contact remains an alternative requiring hold-during-measurement software changes. The visible ring may be a movable O-ring rather than a rigid shoulder; verify before using it as a locating feature. PalmSens lists the potentially similar PS101–104 family as 6.35 mm OD with a brass terminal and adjustable O-ring, but the photograph does not establish that model (https://www.palmsens.com/product/ps101-104-series-standard-disc-electrodes-we/). Obtain the electrode model and measured body diameter, ring/shoulder diameter/thickness and mobility, body/shoulder-to-tip length, terminal diameter and exposed length before revising printable parts or specifying purchased contacts.

## Applied workspace workflow — 2026-10-14

User approved saving explorer results into Settings to guide fixture placement. Implemented explicit preview/apply of the full map and a rectangle supported across the current required Z stroke, persistent map provenance, shaded calibration/workspace support, per-station supported/rejected/unknown feedback, and previewed rectangular/radial rack placement. Numerical radial bounds remain active; saved-map feedback is advisory and corner-based interiors remain untested. Rack fitting preserves spacing/layout and checks all exported slots but not physical footprints or obstacles. All profile operations are non-moving, clear readiness as appropriate, and retain current station Z/Travel Z.

Mocked checks cover Z/R coverage, holes and unknowns, rectangular/radial fitting, JSON roundtrip, apply previews and no hardware actuation; firmware support and physical accuracy remain unverified. The user also confirmed the electrode O-ring slides with resistance and can be removed for a proper holder. Photo-based body/terminal lengths of approximately 60/20 mm remain estimates; the separate split-holder prototype now uses these dimensions, but physical fit remains unverified.

## Workspace boundary precision — 2026-10-14

The user reported configured-workspace rejection at X=200, Y=0, Z=-3.57628e-06 mm after configuring with Workspace explorer. This is consistent with numerical noise around a zero Z minimum; the actual profile and controller reachability at that pose have not been verified. Pose and calibration checks now allow 0.0001 mm numerical error at Cartesian/radial boundaries, while retaining original coordinates for controller checks. Regression checks use mocked feedback and retain rejection of meaningful out-of-bounds values and controller-rejected samples.

## Initial-electrode split holder prototype — 2026-10-14

The user raised a seating concern on 2026-10-14: a stationary spring contact may miss the narrow band or resist top-down insertion enough to leave the released carrier incompletely seated. Reliable band alignment and seating under contact load remain unresolved requirements. A deeper locating pilot with a contact band below the support shoulder and opposed compliant side contacts is a proposal only; no revised geometry, chosen contact force or physical seating result is established.

The latest user sketches (2026-10-14) place an annular copper contact on the bottom face of the holder's narrower lower section, inside a cup-shaped removable cell-cap insert. The user explicitly confirmed **fixed metal bars**, not spring-loaded pins: two opposed radial bars lie on the insert's bottom ledge and connect in parallel to the same WE lead through internal wire channels. A wire inside the holder connects the bottom ring to the electrode terminal socket. The central opening clears the electrode; the surrounding insert guides placement. This supersedes the assistant's upright spring-pin interpretation and its spring-force calculation.

For this fixed-bar concept, the copper ring must reach the mechanically supported bars before any other plastic stop prevents contact. Bar coplanarity, ring flatness, guide clearance, available contact pressure and repeatable seated height need physical checks. Either bar may preserve electrical contact when the other loses it, but shared band/wire faults remain. Trial dimensions and printable geometry are recorded below; the assembly remains physically unvalidated.

The user also specified a small wire passage through the holder from the bottom copper ring to the electrode's top terminal. Size it for the selected insulated wire and keep it clear of the electrode bore and clamp hardware. A recessed ring connection and wire strain relief are proposed so the joint cannot create a high spot on the seating/contact face; passage and recess dimensions remain to be selected.

The insert must include space for two symmetric insulated-wire routes, one from each fixed bar, joining at a single connection point for the potentiostat WE cable. A recessed junction pocket and cable strain relief are proposed. The updated `cad/electrode-holder/fixed-contact-concept.svg` / `.png` drawing shows these requirements; regenerate it with `fixed_contact_concept.py`. It is a concept schematic, not the existing STL geometry.

On 2026-10-14 the user requested printable holder/insert prototypes and authorised standard trial hardware dimensions because none were available to measure. Implemented a separate nine-piece dry bench kit in `cad/fixed-contact-prototype`: split holder, fixed-bar insert, taped wiring cover, tip-clearance stand and four coupon solids. Selected nominal hardware is an 8 × 14 × 1 mm copper washer, two 5 × 10 × 1 mm copper tabs cut from sheet, M3 clamp hardware and insulated wire up to 1.4 mm OD. The 24 mm holder has an 18 mm lower section; the insert has an 18.6 mm guide, 34 mm body and 38 mm flange. Metal contact leaves 1.8 mm flange-to-rim clearance; the 60 mm stand gives an estimated 17.8 mm tip clearance for a 60 mm body. The exact terminal socket and actual electrode length still need measurement.

The generated kit includes individual STLs, coupon/complete print plates, JSON configuration/manifest, assembly instructions and exact mesh previews. Nominal geometry and export checks pass for all nine solids, metal/hardware/wire clearances, contact area, insertion, stand/cover fit and a roughly 204 × 91 × 60 mm plate. Full unit suite: 52 passing tests; no physical hardware used. Contact resistance, fit, stability and gripper retention remain untested. The insert is not fitted to the real cell cap or sealed for wet use, and the earlier shallow rack-seat interface is not preserved by this deeper holder.

Implemented a separate parametric CAD design in cad/electrode-holder using the user's confirmed 6 mm diameter, removable O-ring, and photo-estimated 60 mm body / 20 mm terminal lengths. Two clamp halves use M3 hardware, a 22 mm main body, 26 mm sloped flange, 18 × 1.5 mm locating pilot, 3 mm recessed dry contact band and external wire channel. Files include individual halves, a compact paired print plate, split bore coupon, manifest, exact mesh preview, and SVG/PNG electrical assembly instructions. This is a standalone prototype; the UI's older holder/rack exporter and lab settings are unchanged.

Nominal mesh checks cover the existing 18.4 × 1.5 mm rack seat, rod/hardware clearance, closed connected solids, bed fit and assembly/print transforms. The new holder leaves approximately 41.5 mm below the deck at the proposed collar position. The larger grip/flange, print tolerances, clamp retention and cell geometry need physical trials. Remaining electrical interfaces are the measured terminal socket and chosen compliant contact/cell mount. The contact must retract past the flange (3 mm lateral allowance proposed) without snagging or disturbing seating; its permitted travel/force, electrical continuity and dry-zone clearance are unverified. No automatic continuity detection or hardware operation was added.


## Publication direction — 2026-10-14

The user intends a technical platform paper demonstrating affordable automated **electrode screening**, rather than primarily a chemistry-discovery study. Device and Digital Discovery are candidate journals, not confirmed submission targets. The distinction from ExpFlow is exchange of independently prepared working electrodes rather than robotic vial exchange around a fixed electrode assembly. The user estimates a little over 32 electrodes per run; this remains a target capacity, not a demonstrated unattended run or measured throughput.

HER catalyst screening and glucose oxidation are proposed application demonstrations; materials, electrolytes, controls and protocols remain undecided. Charge-storage coating screening is an additional proposal, not selected scope. Suggested study planning is 32 slots (7 conditions × 4 independent electrodes + 4 controls) or 36 slots if physically feasible (8 × 4 + 4 controls). These counts are design suggestions, not sample-size power calculations or completed experiments. Validate independent preparations, between-day performance, manual/automated agreement, contact reliability, full-cycle success, hands-on time and actual total/incremental cost. Repeated scans and reused dummy-electrode handling cycles must be reported separately from independent electrodes and material formulations. Shared-electrolyte contamination/depletion and electrode-order effects require validation; rinsing alone does not reset the test cell. No chemistry campaign or new acquisition capability was implemented by this discussion.

## Glass-cell cap prototype — 2026-10-23

The user supplied ruler photographs of a glass-cell cap and its black electrode-retaining fitting, and requested a printed replacement retaining two RE/CE ports and both gas ports with space for the robotic WE holder. The user reports the cap itself screws into the glass, estimates the main flange as 55 mm and the large thread as approximately 43 mm diameter / 2 mm crest spacing, confirms the black fitting's opening as 7 mm, and estimates its thread as 9 mm with six layers per centimetre. These are not caliper/gauge measurements; the black-fitting pitch/profile and glass-thread profile/handedness remain unconfirmed. The later 55 mm estimate supersedes apparent 61–64 mm photo scaling affected by parallax.

Implemented `cad/robot-cell-cap`: separate upper deck and screw-in base joined by three M3 bolts/nuts in blind pockets, two recessed RE/CE fittings, two trial 4 mm gas bores, and a raised 34.4 mm socket for a compact 36 mm-flange contact cartridge. The existing holder halves, metal contact dimensions and wire cover are reused; the older 38 mm cartridge flange slightly intersects a fixed-electrode path and must not be substituted. Port centres are rearranged. The default base uses 42.7 mm trial crest diameter / 2 mm pitch and a provisional 9 mm / 1.667 mm-pitch black-fitting interface. Three large-thread and three small-fitting gauges support fit checks before the base is printed.

All twelve individual solids and the assembly/gauge/complete plates pass mesh/interface/export checks; full unit suite is 57 passing tests. The approximately 195 × 175 × 19.3 mm complete plate fits the configured Ender-3 V2 bed. Original photos stay outside Git; ruler landmarks, user estimates, configuration, manifest, previews, local port layout and print package are recorded. Physical thread fit, original gasket compression, black-fitting grip, printing tolerances, wet compatibility, gas tightness and gripper clearances remain untested. With the estimated 60 mm electrode body, the modelled tip is 17.9 mm below the gasket land and only 7.9 mm beyond the threaded plug end; actual electrode length, liquid level and cell interior must establish immersion. No hardware operation or profile/taught-Z change was made.

## Optional application workspace and screening preset — 2026-11-26

The user reports that extending the configured application workspace allowed further robot movement; this supports an application-bounds explanation for that observation, not a newly measured physical envelope. They requested optional workspace enforcement and a 32-electrode layout with measurement/rinse stations.

Implemented an off-by-default, persisted workspace-enforcement switch. Older profiles without the field also default to off; stored bounds and saved maps remain available. Controller preflight remains independently enabled by default; controller rejection, alarm/stall/timeout handling, homing/readiness and Stop remain intact. Maps are advisory and applying one does not silently turn enforcement on. Diagrams hide disabled bounds and identify the mode.

Added a non-moving 32-slot preset in Robot calibration and a loadable example JSON: two radial rows of 16 at 210/250 mm, 10° spacing from −75° to +75°; cell (140, −70, 0), rinse (140, 70, 0), rack Z 0 and Travel Z 40 mm. These are provisional tool coordinates, not validated fixture heights or controller reach. UI application preserves hardware/acquisition/manufacturing settings and clears readiness. No physical robot testing was performed.

Verification: 61 unit tests and both offscreen UI checks passed using simulation/mocked devices, including movement beyond disabled bounds, retained controller rejection, optional-bound persistence, old-profile defaults and non-moving 32-slot preset application. Normal and compact UI screenshots were reviewed.

## Guided layout planning — 2026-11-26

The user reported controller rejection of the provisional 32-slot route at XYZ/R (176.7, −32.46, 40, 0). It is a rejected sampled pose, not proof of a particular joint limit or an absolute reach envelope. They requested implementation of automatic layout fitting and transfer routing to reduce manual coordinate trial and error.

Implemented Find a working layout in Manual robot and Robot calibration: fresh teaching of rack Z, cell/rinse XYZ and clearance Z; requested electrode count/minimum spacing; controller-only bounded radial search; checked intermediate transfer segments; preview and explicit apply. Cell/rinse positions and taught heights are preserved. Rejected vertical strokes and disconnected route networks have specific feedback. Smaller proposals report best capacity in the sampled regular-layout search, not global robot capacity. Failed/cancelled/unsupported searches do not apply a partial layout or change homing merely because of cancellation.

Saved transfer graphs are consumed by both route preflight and experiment/rehearsal execution. Editing relevant settings makes them stale; there is no silent fallback to a rejected straight chord. Current poses outside the saved network require replanning. Physical fixture, cable and electrode clearance still requires commissioning; approximate footprint checks are not a collision model. No physical robot testing was performed.

Verification: 69 unit tests and three offscreen UI checks cover rejected straight chords with accepted waypoint alternatives, vertical-interior limits, bounded capacity, stale/out-of-coverage plans, subset rehearsal, exact preflight/execution sequence agreement, fresh teaching, preview/apply/persistence, unsupported firmware and read-only cancellation. Normal and compact wizard screenshots reviewed; all devices were simulated or mocked.

## Optional route simplification and queued transfers — 2026-11-26

The user reports stop-and-go motion through the planner's intermediate waypoints and requested separate checkboxes for simplification and continuous movement. Implemented both under Robot calibration → Transfer motion options, off by default. Simplification queries shortcuts and preserves the base graph; it can be prepared through Check planned route for an existing plan and is refreshed before hardware batches. Queued transfers remove application waits between horizontal MOVL waypoints, using reported free space and a rolling 16-command window. Lifts, descents and gripper operations retain completion barriers. Cancellation, malformed upload responses, controller rejection, alarms and endpoint mismatch are covered by mocked tests.

Continuous motion is explicitly labelled **queued transfers**, not native CP blending. The reviewed official Lite virtual implementation has a stub CP motion handler; actual firmware-native blending support and achieved motion smoothness are unverified. The controller may still slow or stop at corners. No physical hardware was used for development or tests.

Verification: 77 unit tests and three offscreen UI checks passed with simulated/mocked devices. Coverage includes shortcut rejection/retention, original-route toggle, saved shortcuts, bounded queue refilling, unsupported feedback, upload cancellation/index errors, runtime alarm/cancellation, endpoint mismatch, horizontal-only blocks and shared preflight/execution geometry. Normal and compact option screenshots reviewed.
