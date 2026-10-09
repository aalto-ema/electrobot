# Printable pickup collar and probe bracket

All dimensions are millimetres. These are **provisional prototypes, not fitted Magician Lite accessories**. Only the nominal 6 mm rod is supplied by the project; every other fit dimension is an assumption. The rigid mounting neck assumed here has not been confirmed to exist on this gripper. Do not clamp the soft fingers, hoses, moving parts or an unsuitable robot shaft.

## Parts

- `pickup_collar.stl`: 18 mm body, 24 mm retaining flange, 17 mm total height. Blind 6.3 mm rod socket, 13 mm deep; 2 mm wire passage to an 8.2 mm diameter, 1 mm deep top contact-pad recess. A radial 2.5 mm pilot hole allows a tapped M3 set screw if the actual carrier can tolerate it. This hole is not a printed thread. Secure the rod mechanically; the conductor must emerge from its top into the pad recess. Socket depth does not set cell immersion depth.
- `probe_bracket_front.stl`: clamp half with C-shaped support and probe plate. Assumed neck diameter 20 mm plus 0.4 mm diametral clearance, clamp height 12 mm, radial wall 4 mm. External support centerline is 45 mm from the rod axis; probe plate center is 45 mm below the clamp midpoint. Assumed probe mounting hole is 6.2 mm in a 5 mm thick plate. Use a probe whose flange/nuts retain it and whose insulated housing fits the chosen bracket; do not assume a bare pogo pin fits this hole.
- `probe_bracket_rear.stl`: mating clamp half. Two 3.4 mm through-holes per half accept M3 clamp bolts and separate nuts/washers. Determine bolt length from the actual assembly. No captive nuts or printed threads.
- `parts-preview.png` / `.svg`: separate parts, not an assembly or collision check.
- `mesh-validation.json`: generated geometric checks, not a mechanical or electrical qualification.

The contact pad, conductor, probe, bolts and cable are separate components. A pad must be securely retained and electrically joined to the conductor; the recess alone does not provide retention. Select attachment and insulating materials after confirming the carrier construction and electrolyte. The probe load must not exceed measured grip retention. The soft fingers must actually engage beneath the flange for it to prevent slip.

## Measurements needed

Use the intended vertical tool orientation. Define **Z=0 as the midpoint of the proposed rigid clamp**, with positive Z downward along the rod axis. The generator uses downward as negative model Z; `bracket_drop` is the positive distance below the clamp midpoint.

| Measure | What to report / why |
|---|---|
| Rigid mounting surface | Diameter and uninterrupted axial length of any stationary cylindrical neck, plus nearby hose/fitting locations. If there is no suitable neck, report rigid-body width/depth/height and available mounting holes, thread sizes and center-to-center spacing; the mount must then be redesigned. |
| Neck versus rod center | Whether the mounting neck is concentric with the intended rod axis; measure any X/Y offset. This prototype assumes concentric axes. |
| Finger grip range | Smallest and largest cylinders held reliably at the actual operating pressure, and the finger contact height along each cylinder. This sets collar diameter and height. |
| Open/closed envelope | Maximum radial extent from the rod axis and upper/lower Z limits of all three fingers, both open and closed, including intermediate movement. Also indicate a clear angular gap for the bracket upright. |
| Central access | Available space above the collar/contact pad, between the fingers and rigid body: clear diameter, Z range, and any central obstruction. The probe needs space here. |
| Pickup height | Distance from clamp midpoint to the intended top contact-pad surface when the collar is securely gripped. Include repeatability or estimated variation. Probe plate position depends on this and the probe protrusion. |
| Probe | Part number/drawing, mounting diameter/thread, flange/nut sizes, total length, tip projection below its mount, recommended compression, maximum travel, spring force, electrical rating, and insulation arrangement. |
| Rod and conductor | Actual rod diameter and tolerance, solid/hollow construction, wall thickness, top-end construction, conductor diameter and how it connects to the active electrode; whether a set screw can be used. |
| Cell and rack clearance | Top-pad height above the cap, cap opening/seat geometry, rack pitch, and free space around the collar. The 24 mm provisional flange will not fit the application's current 22 mm rack pitch without interference; increase pitch or reduce/redesign the collar after measuring grip range. |
| Printing process | Printer/material, nozzle size, and measured hole-fit allowance from a small calibration print. Current clearances are placeholders. |

Top and side photographs with a ruler are useful, but caliper dimensions are preferable. Do not cycle the gripper near calipers or fingers; measure it stationary in each state.

## Regeneration

Edit `dimensions.json`, then run from the repository root:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python cad/gripper/generate.py
```

On Windows, use `.venv\Scripts\python.exe cad\gripper\generate.py`; Qt normally needs no offscreen setting there. This uses the project's existing CAD libraries, without OpenSCAD. The Python source plus JSON dimensions are the editable parametric design; STL files are regenerated outputs.

For initial slicing, put the collar flange on the bed and inspect support for the blind bore roof. Lay bracket halves on a flat face that gives strong continuity along the C-shaped support, then inspect supports around the clamp and probe hole. Holes may need finishing. Slicer preview and a fit coupon should precede a full print. All parts remain in the dry zone. Verify fit, screw retention, finger clearance through the full motion, probe compression, grip retention and electrical continuity before robot operation with a cell.

The application currently releases the carrier in the cell. This contact arrangement requires a future hold-during-CV workflow; these CAD files do not change robot behavior or calibration.
