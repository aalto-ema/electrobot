# Collar-supported lattice rack concept

The SVG/PNG explain a proposed replacement for the application's blind-socket rack. This is a concept, not an exported STL or an implemented rack option.

Support the existing pickup collar by its bottom face in a shallow recess. The rod passes through a clearance hole and hangs freely. Leave the cylindrical grip surface, upper flange and top electrical pad exposed. Connect individual seats with narrow ribs following the rectangular or radial slot coordinates. Use a few legs outside all rod paths, with mounting feet; divide a large rack into printable sectors later.

Provisional starting dimensions based on `../gripper/dimensions.json`: 18 mm collar body, 24 mm upper flange, 18.4 mm locating recess, 1.5 mm locating depth and approximately 7 mm rod passage. The 14 mm body leaves approximately 12.5 mm exposed above the recess. Seat height must exceed the actual rod length below the collar by a chosen clearance, e.g. 50 + 10 = 60 mm. Neither clearance nor grip fit has been tested. Trial spacing of 30–35 mm is only an assumption; the full pump-off finger envelope, positioning error and neighboring carriers determine final spacing.

Before printable CAD: measure actual collar dimensions, finger contact height and radial envelope in the relaxed and closed states, and hanging electrode length. Confirm that the collar reliably retains the rod and that the available body height accommodates all three fingers. If the recess gives insufficient vertical alignment, add a lower non-contact clearance guide around an inactive shaft region; never support the active tip. Rack coordinates and gripping Z require commissioning after assembly.

Material savings have not been quantified. Compare equal-capacity mesh volumes and slicer estimates after detailed geometry and stiffness have been validated. The existing cell/probe integration and release-in-cell workflow remain separate design questions.
