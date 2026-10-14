# Three-electrode rack: one compact print file

Open **`three-electrode-rack-kit.stl`** in your slicer, keep its relative arrangement and use mm at 100% scale. The single file contains **nine separate, closed solids**, not an assembled rack:

| Label on `plate-layout.png` | Quantity | Part |
| --- | --- | --- |
| R | 1 | Three-seat radial top support |
| F1–F3 | 3 | Identical detachable fork feet, with fixing tabs |
| H1–H3 | 3 | Pickup holders for nominal 6 mm rods |
| A | 1 | Nominal holder/foot fit coupon |
| B | 1 | Slightly looser holder/foot fit coupon |

The occupied footprint is approximately **126.5 × 132.1 mm**, maximum height **94.5 mm**. The user specified a **Creality Ender-3 V2 with Cura**. The layout is centred on its nominal 220 × 220 mm bed, with at least 8 mm between part bounding boxes, and fits its nominal 250 mm build height. The three tall feet are grouped into a 72 × 48 mm region; after the short components finish, the remaining printing stays around this group. A search of shelf orders/rotations favours small area and a compact shape. This reduces geometric separation; actual travel and print order depend on the slicer and have not been simulated as printer toolpaths.

## Slicing

- In Cura, use your Ender-3 V2 printer configuration and actual nozzle/material profile. Open the combined STL, keep scale at 100% and retain its relative arrangement. Search for **Print Sequence** in Custom settings and select **All at Once**. Slice and inspect Preview before saving G-code for your printer.
- Use normal **layer-by-layer / all objects together** printing for this prepared layout. The STL contains no temperature, speed, material, support or printer-specific profile and is not G-code.
- Keep the top and coupons flat, feet upright on their bases, and holders flange-down as supplied. Do not auto-arrange the individual shells if you want to retain the compact layout. If your slicer asks whether to split the file, preserve the part coordinates.
- Inspect the slicer preview, especially adhesion of the tall 6 mm foot columns, small underside socket bridges, holder contact recess and all gaps. A foot brim may help; choose it in the slicer and check its footprint rather than assuming the geometry includes one.
- Cura's **One at a Time** completes one object before starting the next. That mode requires the actual printhead/gantry clearances and object order, beyond checking the build volume. This tightly packed file is **not validated for complete-object sequential printing**; use **All at Once**. The 94.5 mm feet especially require clearance validation before considering sequential printing. Do not raise Cura's gantry-clearance settings simply to bypass a collision restriction.

References: [Creality Ender-3 V2 dimensions](https://www.creality.com/blog/ender-3-v2-vs-cr-6-se-comparison-what-are-the-differences-and-similarities); [UltiMaker's explanation of Print Sequence and gantry-height limits](https://support.ultimaker.com/s/article/1667337612195) (the general print-sequence note, not the material-specific TPU recommendations).

## Provisional dimensions and assembly

The holder has an 18 mm body, 24 mm upper flange and 6.3 mm rod socket. The body is 14 mm high plus a 3 mm flange; insertion depth is 13 mm. A 100 mm rod leaves 87 mm hanging. The assembled seat is 97 mm above the bench, giving 10 mm tip clearance. Each foot prints separately at 94.5 mm including its pegs; the top is 6 mm thick and seats on the column shoulders. These physical heights are not robot tool Z settings.

Coupon A matches the top support: holder recess Ø18.4 mm, peg sockets Ø4.3 mm. Coupon B has recess Ø18.6 mm and peg sockets Ø4.5 mm. Both use a 1.5 mm holder locating depth; foot pegs are nominal Ø4 mm. A is gold and B orange in the diagram; labels are not embossed. They are identifiable by position before removal and by measured recess size afterward. If only B fits well, adjust the printing clearances and regenerate the top rather than assuming the nominal top also fits.

Push paired foot pegs into the underside top sockets, then fix each foot's mounting tab to the bench using a suitable fixing or tested fixture. The push fits are provisional and are not locking joints. Seat the holder bottoms in the shallow recesses, leaving their bodies accessible to the gripper. The rods and active tips hang freely. Mechanically retain the rods; the holder's radial pilot hole is not a thread. Metal pads, conductors, retention screws and electrical probes are not printed parts.

See `parts/ASSEMBLY.md` and `parts/rack_manifest.json` for assembly coordinates, rotation, print quantities and component notes. The source rack has exactly three slots on a 200 mm radius at −11°, 0° and +11°. `example-config.json` can be loaded in the app as an uncommissioned profile; teach grip/travel Z and check all physical clearances before motion. The cell cap and nominal 70 mm-high beaker are not automatically compatible with an 87 mm hanging electrode assembly.

## Regeneration and validation

From the repository root:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python cad/three-electrode-print/generate.py
```

On Windows use `.venv\Scripts\python.exe cad\three-electrode-print\generate.py`. Optional `--bed-width`, `--bed-depth` and `--gap` arguments adjust packing; changing holder/rack dimensions requires updating the explicit `Settings` example in this generator. The app's separate-component export remains unchanged.

The generator uses the production rack/holder/foot CAD, reloads the final STL, verifies nine closed connected solids, checks every part is on Z=0, confirms bed fit and checks pairwise bounding-box separation. `plate-manifest.json` records the exact layout and dimensions. These checks do not validate real printer adhesion, stiffness or hardware grip fit.
