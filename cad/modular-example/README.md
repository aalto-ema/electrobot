# 24-electrode modular radial rack

Load `example-config.json` in Settings to inspect this provisional layout. The profile uses three radial rows of eight slots, 36 mm row spacing, 11° angular spacing, and four slots per top module. Robot coordinates are uncommissioned; no physical route or grip fit has been verified.

Print the top files **twice each**, `rack_foot.stl` **18 times**, and `pickup_holder.stl` **24 times**. Start with the optional `rack_fit_coupon.stl`, one foot and one holder before printing the full set. See `ASSEMBLY.md` and `rack_manifest.json` for dimensions, quantities, origins and per-module rotations. The largest top is approximately 182 × 60 × 6 mm, within the configured 220 × 220 mm bed. Feet are approximately 32 × 20 × 94.5 mm and print separately.

The holder uses an 18 mm grip body, 24 mm flange and 6.3 mm rod socket. The 100 mm rod enters the holder by 13 mm, leaving 87 mm hanging; the seat is 97 mm above the bench for 10 mm tip clearance. Include any additional active-electrode projection when setting the hanging length. Metal contact pad, wire and retention screw are separate components; the pilot hole is not threaded. The holder is printed flange down and flipped for assembly.

The STL files are closed connected solids. Peg and seating fits, tall-foot stiffness, grip clearance and electrode retention require physical testing. Feet attach with paired push-fit pegs and each independent module must be secured to the bench; each foot has a mounting tab with a provisional 3.4 mm fixing hole, and there are no inter-module clips. The printed seat height does not determine tool Z; teach actual rack Z and update travel height after assembly. The cell cap and electrical-contact bracket require separate compatibility checks.

Complete modules can be reused when extending to more rows or modules at the same slot coordinates and interface dimensions. Rotated copies with identical geometry share one STL. Changed curvature, pitch, holder/foot interface or module size may require new top files; partial modules may need replacing. Compare geometry IDs in manifests when reusing parts. Identical feet are reusable while their height and interface dimensions remain the same.

Regenerate the files and mesh-based preview from the repository root:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python cad/modular-example/generate.py
```

On Windows, run `.venv\Scripts\python.exe cad\modular-example\generate.py`. The application can generate other configurations through Settings → Rack design → Export rack printing files.
