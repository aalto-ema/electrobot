// Electrobot cap concept. Measure actual rim before printing.
// Print flat face down / skirt up; lead-in faces down during printing.
$fn=128;
rim_d=53.0; clearance=0.8; wall=3.0;
plate=4.0; skirt=6.0;
we_d=6.6; mouth=10.0; re_d=8.0; ce_d=6.0;
port_offset=14.0;
inner=rim_d+clearance; outer=inner+2*wall;
difference() {
 union() {
  cylinder(h=plate,d=outer);
  translate([0,0,-skirt]) difference() {
   cylinder(h=skirt+.01,d=outer);
   translate([0,0,-.01]) cylinder(h=skirt+.03,d=inner);
  }
 }
 translate([0,0,-.1]) cylinder(h=plate+.2,d=we_d);
 translate([0,0,plate-2]) cylinder(h=2.01,d1=we_d,d2=mouth);
 translate([-port_offset,0,-.1]) cylinder(h=plate+.2,d=re_d);
 translate([port_offset,0,-.1]) cylinder(h=plate+.2,d=ce_d);
 // Open notch for pouring spout and vent; align notch to beaker spout.
 translate([-6,-outer/2-1,-skirt-.1]) cube([12,outer/2-inner/2+3,skirt+plate+.2]);
}
