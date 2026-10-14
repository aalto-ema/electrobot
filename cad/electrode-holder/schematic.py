"""Generate dimension-linked SVG/PNG instructions, not an electrical qualification."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QImage,QPainter,QColor


def schematic(d,folder):
    # Structural side view uses mm-scaled geometry; wiring and mounting are illustrative.
    x=245; scale=5; zero=450
    z=lambda value:zero-value*scale
    body_top=d['total_height']; tip=body_top-d['electrode_body_length_estimate']
    terminal_top=body_top+d['terminal_length_estimate']
    radius=d['body_diameter']/2*scale; flange=d['flange_diameter']/2*scale
    body_r=d['electrode_body_diameter']/2*scale
    ring=d['contact_z']+d['contact_width']/2
    parts=['''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1120" viewBox="0 0 1400 1120">
    <defs><style>text{font-family:Arial,sans-serif;fill:#233f4c;font-size:19px}.title{font-size:32px;font-weight:bold}.head{font-size:23px;font-weight:bold}.small{font-size:16px}.dim{stroke:#587783;stroke-width:1.5;fill:none}.wire{stroke:#d47623;stroke-width:5;fill:none;stroke-linejoin:round}.leader{stroke:#587783;stroke-width:1.5;fill:none}</style></defs>
    <rect width="1400" height="1120" fill="#f5f8fa"/>
    <text x="35" y="45" class="title">6 mm electrode holder + stationary electrical contact</text>
    <text x="35" y="77">Prototype v1 · printed split carrier; purchased electrical parts · no robot-mounted cable</text>
    <rect x="25" y="100" width="625" height="655" rx="15" fill="white" stroke="#d2dfe5"/>
    <rect x="675" y="100" width="700" height="655" rx="15" fill="white" stroke="#d2dfe5"/>
    <text x="45" y="135" class="head">A. Seated in the cell fixture — side view</text>
    <text x="45" y="163" class="small">Electrode upright; electrical band stays above liquid.</text>
    ''']
    def rect(a,b,w,h,fill,stroke='#56717e'):
        parts.append(f'<rect x="{a}" y="{b}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    def text(a,b,t,cls=''):
        parts.append(f'<text x="{a}" y="{b}" class="{cls}">{t}</text>')
    def line(a,b,c,e,cls='leader'):
        parts.append(f'<path d="M {a} {b} L {c} {e}" class="{cls}"/>')
    rect(100,z(d['pilot_height']),345,24,'#dbe8ed')
    # Clearance/pilot seat, simplified cap cross section
    rect(x-radius-1,z(d['pilot_height']),2*radius+2,12,'white','white')
    rect(x-body_r,z(body_top),2*body_r,(body_top-tip)*scale,'#435665')
    rect(x-radius,z(body_top),2*radius,(body_top-d['pilot_height'])*scale,'#c1b4e0')
    pilot_r=d['pilot_diameter']/2*scale
    rect(x-pilot_r,z(d['pilot_height']),2*pilot_r,d['pilot_height']*scale,'#c1b4e0')
    rect(x-body_r,z(body_top),2*body_r,body_top*scale,'#435665')
    parts.append(f'<polygon points="{x-radius},{z(d["pilot_height"])} {x-flange},{z(d["pilot_height"]+d["flange_thickness"]/2)} {x-radius},{z(d["pilot_height"]+d["flange_thickness"])} {x+radius},{z(d["pilot_height"]+d["flange_thickness"])} {x+flange},{z(d["pilot_height"]+d["flange_thickness"]/2)} {x+radius},{z(d["pilot_height"])}" fill="#c1b4e0" stroke="#56717e" stroke-width="2"/>')
    rect(x-body_r,z(d['pilot_height']+d['flange_thickness']),2*body_r,d['flange_thickness']*scale,'#435665')
    rect(x-radius,z(d['contact_z']+d['contact_width']),2*radius,d['contact_width']*scale,'#d7954f')
    # Ring is a surface contact: show material on the outer wall, not through the rod.
    rect(x-body_r,z(d['contact_z']+d['contact_width']),2*body_r,d['contact_width']*scale,'#435665')
    rect(x-2,z(terminal_top),4,d['terminal_length_estimate']*scale,'#d5ac46')
    rect(x-9,z(terminal_top),18,28,'#c7d1d8')
    parts.append(f'<path d="M {x-9} {z(terminal_top)+14} H {x-radius-15} V {z(ring)} H {x-radius}" class="wire"/>')
    # Purchased spring and fixture tower; not a measured bracket
    rect(405,z(ring)-14,17,z(d['pilot_height'])-z(ring)+14,'#dbe8ed')
    parts.append(f'<path d="M {x+radius} {z(ring)} h 27 l 8 -8 l 8 16 l 8 -16 l 8 8 H 405" stroke="#b67b2e" stroke-width="3" fill="none"/>')
    parts.append(f'<path d="M 423 {z(ring)} H 465 V 310 H 590" class="wire"/>')
    text(470,300,'To WE lead')
    text(48,210,'Removable socket*'); line(220,214,x-7,z(terminal_top)+12)
    text(338,247,'Metal terminal'); text(338,269,'≈20 mm exposed','small'); line(334,276,x+3,z(body_top+8))
    text(48,307,'Short insulated wire'); text(48,329,'Rear groove; shown offset','small')
    text(345,350,'Grip upper body'); text(345,373,'22 mm OD; upper gripping band','small'); line(340,357,x+radius,z(body_top-3))
    text(452,401,'Spring contact*'); line(448,406,370,z(ring))
    text(48,483,'26 mm flange'); line(180,478,x-flange,z(4))
    text(335,490,'Cell cap / fixture*')
    text(335,526,'Remove the O-ring.')
    text(335,553,'6 mm body confirmed.'); text(335,578,'≈60 mm body length.','small')
    line(330,554,x+body_r,565)
    parts.append('<path d="M 115 584 H 438" stroke="#38a4ba" stroke-width="2" stroke-dasharray="7 5"/>')
    text(335,611,'Illustrative liquid level','small')
    text(48,695,f'Tip ≈{d["electrode_body_length_estimate"]-body_top+d["pilot_height"]:g} mm below deck at this collar position.','small')
    text(48,721,'*Socket, spring and cap mounting remain to be selected/measured.','small')
    text(700,135,'B. Assembly and wiring', 'head')
    lines=[
        ('1. Trial-fit the printed halves','Remove the O-ring. Fit around the upper insulating body.'),
        ('2. Clamp mechanically','Two M3 × 12 bolts, head washers and captive nuts; tighten gently.'),
        ('','The gap must remain; do not crush the electrode body.'),
        ('3. Make the dry contact band','Wrap a 3 mm wide copper strip in the recessed groove.'),
        ('','Attach its wire before fitting; keep solder bumps off the spring track.'),
        ('4. Connect the terminal','Use a removable socket matched to the measured pin diameter.'),
        ('','Insulate the socket/wire joint; do not solder to the electrode pin.'),
        ('5. Fit the stationary contact','On the CELL fixture: allow at least 3 mm lateral retraction.'),
        ('','Clear the flange, then press on the band; test force and clearance.'),
        ('6. Test with the potentiostat disconnected','Check terminal-to-band continuity and stable contact when seated.'),
        ('','Check the band is isolated from clamp bolts and other electrodes.'),
        ('7. Commission the mechanical sequence','Confirm release/retrieval, wire retention and full finger clearance.')]
    y=185
    for title,detail in lines:
        if title: text(700,y,title); y+=27
        text(700,y,detail,'small'); y+=30
    parts.append('''<rect x="25" y="780" width="1350" height="310" rx="15" fill="#e7f1f4"/>
    <text x="45" y="818" class="head">C. Electrical path — the robot only transports the carrier</text>
    <g fill="white" stroke="#9bb9c5" stroke-width="2">
    <rect x="45" y="845" width="220" height="65" rx="8"/>
    <rect x="315" y="845" width="260" height="65" rx="8"/>
    <rect x="625" y="845" width="280" height="65" rx="8"/>
    <rect x="955" y="845" width="380" height="65" rx="8"/></g>
    <text x="65" y="883">Electrode terminal</text><text x="332" y="883">Socket → wire → band</text>
    <text x="642" y="883">Cell-mounted spring contact</text><text x="975" y="883">Existing potentiostat WE lead</text>
    <path d="M 265 878 H 315 M 575 878 H 625 M 905 878 H 955" class="wire"/>
    <text x="45" y="953">Printed: two clamp halves. Purchased: bolts, nuts, washers, band, wire, socket and stationary contact.</text>
    <text x="45" y="984">Keep the band/socket above electrolyte AND rinse level. Cap seat carries weight; the contact does not set immersion.</text>
    <text x="45" y="1015">Copper foil is a prototype contact: check oxidation, retention and resistance stability before measurements.</text>
    <text x="45" y="1046">Cell OFF before handling. RE and CE stay connected at the cell. This drawing does not specify instrument connector pins.</text>
    <text x="45" y="1076" class="small">Side-view fixture, terminal width, spring and wiring are explanatory. Printable dimensions come from dimensions.json / manifest.json.</text>
    </svg>''')
    svg='\n'.join(line.rstrip() for line in '\n'.join(parts).splitlines())+'\n'; folder=Path(folder); (folder/'electrical-assembly.svg').write_text(svg)
    app=QApplication.instance() or QApplication([])
    image=QImage(1400,1120,QImage.Format.Format_RGB32); image.fill(QColor('white'))
    painter=QPainter(image); QSvgRenderer(bytes(svg,'utf-8')).render(painter); painter.end()
    image.save(str(folder/'electrical-assembly.png'))
