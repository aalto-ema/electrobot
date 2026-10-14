"""Generate a compact, single-STL three-electrode rack kit; no printer G-code."""
import argparse
from dataclasses import asdict,replace
import itertools
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from electrobot.config import Settings
from electrobot.rack_cad import export_rack
from electrobot.lattice_rack import top_mesh
from electrobot.mesh_utils import connected_solids


def pack(groups,bed_width,bed_depth,gap,margin):
    """Search shelf orders and rotations; keep the three feet grouped together."""
    orders=sorted(set(itertools.permutations('TF CCHHH'.replace(' ',''))))
    best=None
    for rt,rf in itertools.product((0,90),repeat=2):
        rotations={'T':rt,'F':rf,'C':0,'H':0}
        sizes={}
        for key,meshes in groups.items():
            import numpy as np
            bounds=np.array([m.bounds for _,m in meshes]); lo=bounds[:,0].min(axis=0); hi=bounds[:,1].max(axis=0)
            w,h=hi[:2]-lo[:2]
            sizes[key]=(h,w) if rotations[key] else (w,h)
        minimum=max(w for w,h in sizes.values())
        for width in range(math.ceil(minimum),math.floor(bed_width-2*margin)+1):
            for order in orders:
                x=y=row_h=used_w=0.; placements=[]
                for key in order:
                    w,h=sizes[key]
                    if x and x+w>width+1e-6:
                        y+=row_h+gap; x=0; row_h=0
                    placements.append((key,x,y,rotations[key])); used_w=max(used_w,x+w)
                    x+=w+gap; row_h=max(row_h,h)
                height=y+row_h
                if height>bed_depth-2*margin: continue
                # Compact area with a penalty for an elongated layout.
                score=(used_w*height+.25*(used_w-height)**2,max(used_w,height),used_w*height)
                if best is None or score<best[0]: best=(score,placements,used_w,height)
    if best is None: raise ValueError('Parts do not fit this bed with the chosen separation and margin')
    return best[1],best[2],best[3]


def generate(folder,bed_width=220,bed_depth=220,gap=8,margin=10):
    import numpy as np
    import trimesh as tm
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    s=Settings(rack_design='lattice',rack_layout='radial',rack_columns=3,electrodes=3,
               rack_module_slots=3,rack_pitch=36,rack_angle_step=11,rack_start_angle=-11,
               rack_printer_width=bed_width,rack_printer_depth=bed_depth)
    export_rack(s,folder/'parts')
    source=json.loads((folder/'parts/rack_manifest.json').read_text())
    assert source['holder_quantity']==3 and source['foot_quantity']==3 and len(source['modules'])==1
    top=tm.load_mesh(folder/'parts/rack_top_01.stl')
    foot=tm.load_mesh(folder/'parts/rack_foot.stl')
    holder=tm.load_mesh(folder/'parts/pickup_holder.stl')
    nominal=tm.load_mesh(folder/'parts/rack_fit_coupon.stl')
    loose_settings=replace(s,rack_holder_clearance=s.rack_holder_clearance+.2,rack_peg_clearance=s.rack_peg_clearance+.2)
    loose_settings.validate_lattice()
    loose,_,_=top_mesh(loose_settings,{'positions':[(0,0,0)],'supports':[0]})
    loose.export(folder/'parts/rack_fit_coupon_loose.stl')
    # Same shape as the nominal coupon outside; extra clearance is internal.
    fw,fh=foot.extents[:2]; feet=[]
    for number,(x,y) in enumerate(((0,0),(fw+gap,0),((fw+gap)/2,fh+gap)),1):
        mesh=foot.copy(); mesh.apply_translation([x,y,0]); feet.append((f'F{number}',mesh))
    groups={'T':[('R',top)],'F':feet,'C':[('A',nominal)],'H':[('holder',holder)]}
    # Use the larger of the coupon outlines when reserving its rectangle.
    groups['C']=[('coupon_envelope',tm.util.concatenate([nominal,loose]))]
    placements,width,height=pack(groups,bed_width,bed_depth,gap,margin)
    offset=np.array([(bed_width-width)/2,(bed_depth-height)/2,0.])
    placed=[]; records=[]; counts={'C':0,'H':0}
    for key,x,y,angle in placements:
        if key=='C':
            counts[key]+=1; components=[('A',nominal)] if counts[key]==1 else [('B',loose)]
        elif key=='H':
            counts[key]+=1; components=[(f'H{counts[key]}',holder)]
        else: components=groups[key]
        rotation=tm.transformations.rotation_matrix(math.radians(angle),[0,0,1])
        # Normalize the entire group, preserving relative foot positions.
        rotated=[(name,m.copy()) for name,m in components]
        for name,mesh in rotated: mesh.apply_transform(rotation)
        lo=np.array([mesh.bounds[0] for _,mesh in rotated]).min(axis=0)
        # Both coupons reserve the same envelope; normalize each independently.
        translation=offset+np.array([x,y,0.])-lo
        for name,mesh in rotated:
            mesh.apply_translation(translation)
            if not mesh.is_watertight or not mesh.is_volume or connected_solids(mesh)!=1:
                raise ValueError(f'{name} is not a closed connected solid')
            placed.append((name,mesh)); records.append({'label':name,'bounds_mm':mesh.bounds.tolist(),'rotation_deg':angle,
                                                       'volume_mm3':float(mesh.volume)})
    combined=tm.util.concatenate([mesh for _,mesh in placed])
    combined.export(folder/'three-electrode-rack-kit.stl')
    # Reload to validate the actual file, not just in-memory sources.
    loaded=tm.load_mesh(folder/'three-electrode-rack-kit.stl')
    assert loaded.is_watertight and loaded.is_volume and connected_solids(loaded)==9
    for i,a in enumerate(records):
        bounds=np.array(a['bounds_mm']); assert abs(bounds[0,2])<1e-5
        assert bounds[0,0]>=margin-1e-4 and bounds[1,0]<=bed_width-margin+1e-4
        assert bounds[0,1]>=margin-1e-4 and bounds[1,1]<=bed_depth-margin+1e-4
        for b in records[i+1:]:
            other=np.array(b['bounds_mm'])
            dx=max(0,bounds[0,0]-other[1,0],other[0,0]-bounds[1,0])
            dy=max(0,bounds[0,1]-other[1,1],other[0,1]-bounds[1,1])
            assert math.hypot(dx,dy)>=gap-1e-3,(a['label'],b['label'],dx,dy)
    meta={'units':'mm','bed_mm':[bed_width,bed_depth],'parts':records,'closed_solids':9,
          'bounds_mm':loaded.bounds.tolist(),'minimum_part_gap_mm':gap,'bed_edge_margin_min_mm':margin,
          'settings':asdict(s),'coupon_A':{'holder_recess_diameter':s.holder_diameter+s.rack_holder_clearance,
                                       'peg_socket_diameter':s.rack_peg_diameter+s.rack_peg_clearance},
          'coupon_B':{'holder_recess_diameter':s.holder_diameter+loose_settings.rack_holder_clearance,
                      'peg_socket_diameter':s.rack_peg_diameter+loose_settings.rack_peg_clearance},
          'packing':'Shelf-order/rotation search minimizing area and elongation; feet remain a compact group. No toolpath optimization or sequential-print clearance certification.',
          'print_mode':'Layer-by-layer; no printer-specific G-code or complete-object sequential settings are embedded.'}
    (folder/'plate-manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    (folder/'example-config.json').write_text(json.dumps(asdict(s),indent=2)+'\n')
    preview(folder,placed,meta)
    return meta


def preview(folder,placed,meta):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF,QRectF,Qt
    from PySide6.QtGui import QPainter,QImage,QColor,QPolygonF,QFont,QPen
    app=QApplication.instance() or QApplication([])
    image=QImage(1300,1050,QImage.Format.Format_RGB32); image.fill(QColor('#f4f8fa'))
    p=QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    def text(x,y,value,size=19):
        font=QFont(); font.setPixelSize(size); p.setFont(font); p.setPen(QColor('#234452')); p.drawText(QPointF(x,y),value)
    text(40,46,'Three-electrode rack · one compact print plate',30)
    text(40,82,f'9 separate solids in one STL · provisional {meta["bed_mm"][0]:g} × {meta["bed_mm"][1]:g} mm bed · layer-by-layer printing')
    bw,bh=meta['bed_mm']; k=min(760/bw,760/bh)
    def xy(x,y): return QPointF(55+x*k,920-y*k)
    p.setPen(QPen(QColor('#c5d4dc'),1)); p.setBrush(QColor('white')); p.drawRect(QRectF(xy(0,bh),xy(bw,0)))
    for x in range(0,math.floor(bw)+1,20): p.drawLine(xy(x,0),xy(x,bh))
    for y in range(0,math.floor(bh)+1,20): p.drawLine(xy(0,y),xy(bw,y))
    colors={'R':'#8ac5e0','F':'#a8ded6','H':'#c5b9e2','A':'#ebcb8f','B':'#e9ae8d'}
    for name,mesh in placed:
        p.setBrush(QColor(colors.get(name,colors.get(name[0],'#c5b9e2')))); p.setPen(Qt.PenStyle.NoPen)
        for triangle in mesh.triangles:
            p.drawPolygon(QPolygonF([xy(x,y) for x,y,z in triangle]))
        lo,hi=mesh.bounds; center=xy((lo[0]+hi[0])/2,(lo[1]+hi[1])/2)
        text(center.x()-10,center.y()+7,name,20)
    size=[b-a for a,b in zip(*meta['bounds_mm'])]
    lines=['CONTENTS','R — three-seat top support','F1–F3 — identical fork feet','H1–H3 — electrode holders','A — nominal fit coupon','B — looser fit coupon','',
           f'Packed footprint: {size[0]:.1f} × {size[1]:.1f} mm',f'Maximum height: {size[2]:.1f} mm',
           f'Part spacing: at least {meta["minimum_part_gap_mm"]:g} mm','',
           f'Coupon A: recess {meta["coupon_A"]["holder_recess_diameter"]:g} / pegs {meta["coupon_A"]["peg_socket_diameter"]:g} mm',
           f'Coupon B: recess {meta["coupon_B"]["holder_recess_diameter"]:g} / pegs {meta["coupon_B"]["peg_socket_diameter"]:g} mm','',
           'Keep the relative arrangement.','Feet print upright; holders flange down.','Inspect brims, bridges and stability.','',
           'Complete-object sequential printing','needs printer/head clearance settings.','This STL does not encode print order.']
    for n,line in enumerate(lines): text(855,180+n*31,line,18)
    text(55,974,'Top view; labels are shown here only and are not embossed on the printed pieces.')
    text(55,1008,'No temperature, material, speed or printer-specific toolpath is prescribed by this geometry file.')
    p.end(); image.save(str(folder/'plate-layout.png'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bed-width',type=float,default=220)
    parser.add_argument('--bed-depth',type=float,default=220)
    parser.add_argument('--gap',type=float,default=8)
    args=parser.parse_args()
    if min(args.bed_width,args.bed_depth,args.gap)<=0: parser.error('Bed dimensions and gap must be positive')
    metadata=generate(Path(__file__).resolve().parent,args.bed_width,args.bed_depth,args.gap)
    print(json.dumps({'bounds_mm':metadata['bounds_mm'],'closed_solids':metadata['closed_solids']},indent=2))
