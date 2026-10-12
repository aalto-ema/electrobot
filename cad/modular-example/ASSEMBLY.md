# Modular collar-supported rack

Seat height: 97.0 mm. Rod tip clearance: 10 mm.

Print separate files flat on their Z=0 faces. Inspect the slicer; tall fork feet may need a brim. Holder flange goes on the bed; inspect the contact recess on that face.

## Print quantities

- rack_top_01.stl: 2 ×; size 141.8 × 52.0 × 6.0 mm
- rack_top_02.stl: 2 ×; size 161.9 × 55.9 × 6.0 mm
- rack_top_03.stl: 2 ×; size 182.0 × 59.8 × 6.0 mm
- rack_foot.stl: 18 ×; size 32.0 × 20.0 × 94.5 mm
- pickup_holder.stl: 24 ×; size 24.0 × 24.0 × 17.0 mm
- rack_fit_coupon.stl: 1 ×; size 30.3 × 30.3 × 6.0 mm

## Assembly

1. Trial-print one foot, one holder and one small top module. Tune peg and holder clearance to your printer.
2. Insert rods into the holder sockets and mechanically retain them. Pilot holes require finishing/tapping or a suitable insert; the contact pad and conductor are purchased parts.
3. Push the paired foot pegs into the blind underside sockets. Seat the top on the column shoulders. Do not rely on an untested push fit for permanent retention.
4. Rotate each top and its feet by rotation_deg, then position its STL origin at robot_xy_at_stl_origin (manifest). Foot centres are listed in robot XY; paired columns run along module local X. Secure each base using its mounting tab (3.4 mm hole by default, for a separate M3 bolt/washer and suitable bench fixing), or a tested clamp/adhesive fixture. Modules are independent and have no inter-module clips.
5. Seat the holder bottom in the shallow top recess. Confirm all fingers can reach the exposed body in the pump-off state, neighbors clear, and the active tip hangs free.
6. Teach actual rack gripping Z and verify every route. Printed seat height is a physical bench dimension, not the robot tool Z.

Identical top shapes share a file and quantity. Existing full modules can be reused when slot coordinates, holder/foot dimensions and module size stay unchanged. Feet are identical across this export.

Only the files listed in this manifest are part of this export; older files in the directory may be obsolete.
