"""Render exact cap meshes using the existing Qt depth-buffer preview helper."""
import importlib.util
import numpy as np
from electrobot.robot_cell_cap import build_parts,stack_interfaces,at
from electrobot.fixed_contact_cad import cylinder,metal_parts


def preview(d,c,folder):
    spec=importlib.util.spec_from_file_location('contact_preview',folder.parent/'fixed-contact-prototype/preview.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    render_panels=module.render_panels
    meshes=build_parts(d,c);fit=stack_interfaces(d,c)
    mounted=[(meshes['threaded_base'],'#bcc9d6'),(meshes['upper_deck'],'#aec1d0')]
    mounted.append((at(meshes['compact_contact_insert'],[*d['we_xy'],fit['insert_origin_z_mm']]),'#79b69e'))
    for name in ('holder_rear','holder_front'):
        mounted.append((at(meshes[name],[*d['we_xy'],fit['holder_origin_z_mm']]),'#ac96ce'))
    rod=cylinder(c['electrode_diameter'],c['electrode_length_estimate'],fit['electrode_body_top_z_mm']-c['electrode_length_estimate']/2,x=d['we_xy'][0],y=d['we_xy'][1])
    mounted.append((rod,'#465a6b'))
    for xy in d['fixed_electrode_xy']:
        mounted.append((cylinder(7,55,0,x=xy[0],y=xy[1]),'#526878'))
        mounted.append((cylinder(d['fixed_fitting_head_envelope_diameter'],d['fixed_fitting_head_height'],d['fixed_fitting_head_height']/2,x=xy[0],y=xy[1]),'#34404b'))
    for xy in d['gas_xy']:
        mounted.append((cylinder(4,35,2,x=xy[0],y=xy[1]),'#6eabcf'))
    compact=[(meshes['compact_contact_insert'],'#79b69e')]
    ring,bars=metal_parts(c)
    compact.extend((bar,'#c28a43') for bar in bars)
    cover=at(meshes['wire_cover'],[42,0,-3])
    lower=[(meshes['threaded_base'],'#afc0cf')]
    gauges=[(meshes[f'glass_thread_gauge_D{d["cell_thread_nominal_diameter"]-d["cell_thread_diametral_allowance"]:g}_P{d["cell_thread_pitch"]:g}'],'#afc0cf'),
            (at(meshes[f'fitting_thread_gauge_P{d["fixed_thread_pitch"]:.3f}'],[42,0,0]),'#bdac80')]
    render_panels([
        ('A. Assembled: WE, two fixed electrodes, gas',mounted,[.85,-.8,.7], 'Electrode/tube lengths are illustrative; liquid level is unknown.'),
        ('B. Upper deck: raised socket and recessed ports',[(meshes['upper_deck'],'#aec1d0')],[.5,-.75,1.25], 'Two 13 mm access wells reach the black fittings in the base.'),
        ('C. Screw-in base: underside / gasket land',lower,[.65,.7,-.7], f'{d["cell_thread_nominal_diameter"]-d["cell_thread_diametral_allowance"]:g} mm trial diameter, {d["cell_thread_pitch"]:g} mm pitch; fit gauge first.'),
        ('D. Compact insert: top + two fixed contacts',compact,[.2,-.3,2], f'{c["insert_flange_od"]:g} mm flange; same {c["insert_id"]:g} mm guide, holder, bars and wiring.')
    ],folder/'assembly-preview.png','Robot cell cap — exact CAD mesh views',
       f'{d["flange_diameter"]:g} mm main flange | trial OEM threads | blue gas tubes | purple robotic holder | green contact cartridge')
    render_panels([
        ('A. Upper deck — underside on the bed',[(meshes['upper_deck'],'#aec1d0')],[.4,-.6,1.1], 'Pedestal upright; no support inside electrode or gas passages.'),
        ('B. Base — assembly face on the bed',[(at(meshes['threaded_base'],[0,0,0]),'#afc0cf')],[.6,.7,-.9], 'Print flipped: broad flange first, screw thread pointing upward.'),
        ('C. Glass and fitting thread gauges',gauges,[.4,-.8,.8], 'Try the ring gauges by hand before printing the full base.'),
        ('D. Insert underside + separate wiring cover',[(meshes['compact_contact_insert'],'#79b69e'),(cover,'#a8cfc0')],[.5,.7,-1.1], 'Two wires join below the insert; cover is not a liquid seal.')
    ],folder/'print-preview.png','Cap print orientations and fit-first parts',
       'STL units: mm | All at Once printing | print guides and assembled fit checks before any robot use')


def layout(d,folder):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage,QPainter,QColor
    p=['''<svg xmlns="http://www.w3.org/2000/svg" width="1450" height="880" viewBox="0 0 1450 880"><defs><style>text{font-family:Arial,sans-serif;fill:#263f51;font-size:22px}.head{font-size:27px;font-weight:bold}.small{font-size:18px}.line{fill:none;stroke:#587185;stroke-width:2}</style></defs><rect width="1450" height="880" fill="#f4f7fa"/><text x="35" y="48" class="head">Robotic cell cap — local port layout</text><text x="35" y="82">Nominal design dimensions in mm; photograph and user estimates require physical fit checks.</text>''']
    scale=7.2; centre=np.array([350.,365.])
    def circle(xy,diameter,fill,stroke='#526d7e',dash=False):
        x,y=centre+np.array([xy[0],-xy[1]])*scale
        p.append(f'<circle cx="{x}" cy="{y}" r="{diameter*scale/2}" fill="{fill}" stroke="{stroke}" stroke-width="2"'+(' stroke-dasharray="7 5"' if dash else '')+'/>')
    circle([0,0],d['flange_diameter'],'#e0e8ee')
    circle([0,0],d['cell_thread_nominal_diameter'],'none','#8a9eae',True)
    for xy in d['fixed_electrode_xy']:
        circle(xy,d['fixed_fitting_access_diameter'],'white')
    circle(d['we_xy'],d['we_pedestal_diameter'],'#c8e4d7')
    circle(d['we_xy'],d['we_socket_diameter'],'#f4f7fa')
    circle(d['we_xy'],d['we_through_bore'],'#586e7c')
    for i,xy in enumerate(d['fixed_electrode_xy']):
        circle(xy,d['fixed_electrode_through_bore'],'#586e7c')
        x,y=centre+np.array([xy[0],-xy[1]])*scale
        p.append(f'<text x="{x-13}" y="{y+7}" fill="white" style="fill:white">{"R" if i==0 else "C"}</text>')
    for xy in d['gas_xy']: circle(xy,d['gas_bore'],'#6daacb')
    for xy in d['mount_bolt_xy']: circle(xy,d['mount_hole'],'white')
    p.append('<text x="420" y="430" class="small">WE</text><text x="70" y="620">Dashed circle: nominal glass thread</text>')
    rows=[('Main flange',f'{d["flange_diameter"]:g} mm (user estimate)'),('Glass mating thread',f'{d["cell_thread_nominal_diameter"]:g} mm nominal; {d["cell_thread_pitch"]:g} mm pitch'),('Trial male crest diameter',f'{d["cell_thread_nominal_diameter"]-d["cell_thread_diametral_allowance"]:g} mm; truncated trial form'),('Raised WE socket',f'{d["we_socket_diameter"]:g} mm bore; {d["we_pedestal_diameter"]:g} mm outside'),('Compact insert flange',f'{d["compact_insert_flange_diameter"]:g} mm (new insert included)'),('RE / CE',f'Two {d["fixed_electrode_through_bore"]:g} mm through bores'),('Black-fitting access wells',f'{d["fixed_fitting_access_diameter"]:g} mm; fittings recessed in base'),('Black-fitting trial thread',f'{d["fixed_thread_nominal_diameter"]:g} mm nominal; {d["fixed_thread_pitch"]:.3f} mm pitch'),('Gas passages',f'Two {d["gas_bore"]:g} mm bores'),('Deck / base fasteners','Three M3 x 10 bolts + nuts')]
    for i,(label,value) in enumerate(rows):
        y=145+i*46
        p.append(f'<text x="700" y="{y}" style="font-weight:bold">{label}</text><text x="700" y="{y+25}" class="small">{value}</text>')
    p.append('<text x="40" y="689" class="head">Port centres: local X, Y</text>')
    labels=[('WE',d['we_xy']),('RE',d['fixed_electrode_xy'][0]),('CE',d['fixed_electrode_xy'][1]),('Gas 1',d['gas_xy'][0]),('Gas 2',d['gas_xy'][1])]
    for i,(label,xy) in enumerate(labels):
        p.append(f'<text x="{40+i*270}" y="735">{label}: ({xy[0]:g}, {xy[1]:g})</text>')
    p.append('<text x="40" y="790">Positions are rearranged to fit the robotic insert; the original five-hole positions are not copied.</text><text x="40" y="826" class="small">Local origin is cap centre. These are not robot coordinates; re-teach the assembled WE pose. Drawing is not an actual-size template.</text></svg>')
    svg=folder/'port-layout.svg';svg.write_text(''.join(p))
    app=QApplication.instance() or QApplication([]);renderer=QSvgRenderer(str(svg))
    image=QImage(1450,880,QImage.Format_RGB32);image.fill(QColor('white'));painter=QPainter(image);renderer.render(painter);painter.end();image.save(str(folder/'port-layout.png'))
