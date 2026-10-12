# Compact rehearsal profile

`compact-rehearsal.json` is an example for an **empty gripper in a clear workspace**, not real electrode/cell positions. Load using Settings → Load. It preserves Simulation mode and leaves calibration and fixture verification false. Profiles do not connect devices.

Rack slot 1 is (200, 0, 50), cell stand-in (210, 0, 50), and rinse stand-in (210, 10, 50), in mm. Travel Z is 55 mm and tool R is 0 degrees. Only one electrode slot is selected. Station transfers are 10–14.1 mm and vertical station approaches are 5 mm. Velocity and acceleration SDK settings are 10; these are SDK settings, not guaranteed physical mm/s or mm/s². One rinse dip has 0.5 s dwell and cell settling takes 1 s.

These absolute coordinates are not certified safe for the actual arm/tool. Verify them using manual moves first with the work area empty and no electrode or WE cable attached. Homing follows the robot's normal homing path, not this compact route. The first transfer raises from the current pose to Z=55, so it can be larger than 5 mm; manually position near (200, 0, 55, 0) first, after verifying clearance. Keep the actual gripper and any attached bracket clear through the entire route.

If this region is unsuitable, use a verified current pose (X0,Y0,Z0,R0): rack=(X0,Y0,Z0), cell=(X0+10,Y0,Z0), rinse=(X0+10,Y0+10,Z0), travel Z=Z0+5 and tool R=R0, subject to workspace/reach limits. The same warning about the initial approach applies. Do not check readiness boxes until the empty test route and gripper operation have been checked. Actual station settings and readiness must be re-established before running real experiments. Use Robot rehearsal, not Start batch.
