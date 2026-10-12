"""Portable Qt PDF exporter: overview, dimensions and actual-size placement tiles."""
import math
from pathlib import Path
from PySide6.QtCore import QPointF,QRectF,QMarginsF
from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QPainter,QColor,QPen,QFont
from .rack_cad import rack_geometry


def export_placement_pdf(s,path):
    s.validate(); path=Path(path)
    positions,base,_,_=rack_geometry(s)
    circles=[(s.cell_x,s.cell_y,s.beaker_diameter/2,'Cell / WE axis'),
             (s.rinse_x,s.rinse_y,s.rinse_beaker_diameter/2,'Rinse axis')]
    minx,miny,maxx,maxy=base.bounds
    for x,y,r,_ in circles:
        minx=min(minx,x-r); maxx=max(maxx,x+r); miny=min(miny,y-r); maxy=max(maxy,y+r)
    minx=min(minx,-10); miny=min(miny,-10); maxx=max(maxx,10); maxy=max(maxy,10)
    minx=math.floor((minx-5)/10)*10; miny=math.floor((miny-5)/10)*10
    maxx+=5; maxy+=5
    tw,th=260,155
    cols=math.ceil((maxx-minx)/tw); rows_count=math.ceil((maxy-miny)/th)
    if cols*rows_count>100: raise ValueError('Placement exceeds 100 tiles; reduce layout extent')
    writer=QPdfWriter(str(path)); writer.setResolution(144)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    # Full-paper coordinates with our own margins for precise 1:1 scale.
    writer.setPageMargins(QMarginsF(0,0,0,0),QPageLayout.Unit.Millimeter)
    writer.setTitle('Electrobot placement guide'); painter=QPainter(writer)
    if not painter.isActive(): raise IOError('Could not open PDF output')
    painter.scale(144/25.4,144/25.4)
    page=1
    def font(size=3):
        f=QFont('Helvetica'); f.setPixelSize(size); painter.setFont(f)
    def text(x,y,t,size=3,color='#234452'):
        font(size); painter.setPen(QColor(color)); painter.drawText(QPointF(x,y),str(t))
    def line(x,y,a,b,color='#849ba6',width=.25):
        painter.setPen(QPen(QColor(color),width)); painter.drawLine(QPointF(x,y),QPointF(a,b))
    def header(title,note):
        text(12,12,title,5); text(12,19,note,3)
        text(12,202,f'Electrobot | {s.rack_layout} layout | all dimensions mm | page {page}',3)
    def new_page():
        nonlocal page
        if not writer.newPage(): raise IOError('Could not create PDF page')
        page+=1
    def draw_map(transform,clip):
        painter.save(); painter.setClipRect(clip)
        a=transform(s.workspace_x_min,s.workspace_y_min); b=transform(s.workspace_x_max,s.workspace_y_max)
        painter.setPen(QPen(QColor('#bcb4e4'),.25)); painter.drawRect(QRectF(a,b).normalized())
        center=transform(0,0); scale=abs(transform(1,0).x()-center.x())
        for radius in (s.workspace_radius_min,s.workspace_radius_max):
            painter.setPen(QPen(QColor('#cadbe2'),.25)); painter.drawEllipse(center,radius*scale,radius*scale)
        from PySide6.QtGui import QPolygonF
        outline=QPolygonF([transform(x,y) for x,y in base.exterior.coords])
        painter.setPen(QPen(QColor('#635bce'),.4)); painter.drawPolygon(outline)
        for i,(x,y,_) in enumerate(positions,1):
            pos=transform(x,y); painter.setPen(QPen(QColor('#635bce'),.25))
            painter.drawEllipse(pos,(s.rod_diameter+s.rack_socket_clearance)/2*scale,(s.rod_diameter+s.rack_socket_clearance)/2*scale)
            line(pos.x()-1,pos.y(),pos.x()+1,pos.y(),'#635bce'); line(pos.x(),pos.y()-1,pos.x(),pos.y()+1,'#635bce')
            text(pos.x()+2,pos.y()+2,i,2)
        for x,y,r,label in circles:
            pos=transform(x,y); painter.setPen(QPen(QColor('#0e9f92'),.35)); painter.drawEllipse(pos,r*scale,r*scale)
            line(pos.x()-3,pos.y(),pos.x()+3,pos.y(),'#0e9f92'); line(pos.x(),pos.y()-3,pos.x(),pos.y()+3,'#0e9f92')
            text(pos.x()+3,pos.y()+4,label,3)
        line(center.x()-5,center.y(),center.x()+5,center.y(),'#d97706',.5)
        line(center.x(),center.y()-5,center.x(),center.y()+5,'#d97706',.5)
        text(center.x()+3,center.y()-3,'Robot XY datum (0,0)',3)
        painter.restore()
    try:
        header('Electrobot - placement overview','Overview is scaled to fit. Use the later 1:1 tiles for physical positioning.')
        factor=min(190/(maxx-minx),150/(maxy-miny))
        transform=lambda x,y:QPointF(15+(x-minx)*factor,180-(y-miny)*factor)
        draw_map(transform,QRectF(12,25,195,160))
        text(210,32,'Coordinate convention',4)
        notes=['+X right; +Y up in top view.', 'Z values refer to robot tool pose.', 'Orange cross = XY origin datum.', 'Not a measured robot base footprint.', 'Align origin and axis directions', 'using taught robot references.', 'Beaker circles use entered diameters.', 'Cell center assumes central WE port.', 'Robot reach / collisions are not', 'certified by this placement sheet.', '', f'Travel Z: {s.safe_z:g}',f'Tool R: {s.tool_r:g} deg',f'Rack grip Z: {s.rack_z:g}',f'Cell seat Z: {s.cell_z:g}',f'Rinse dip Z: {s.rinse_z:g}',f'Rack printed height: {s.rack_base_thickness+s.rack_post_height:g}']
        for n,t in enumerate(notes): text(210,40+n*7,t,3)
        text(12,191,'Check actual tool offset, gripper/cable clearance, rack seating and glassware before movement. Print tiles at 100%, not Fit.',3)
        # Complete coordinate table, including inactive sockets in final row.
        rows=[('Cell / WE axis',s.cell_x,s.cell_y,s.cell_z),('Rinse axis',s.rinse_x,s.rinse_y,s.rinse_z)]
        rows += [(f'Rack slot {i}'+(' *' if s.first_electrode<=i<s.first_electrode+s.electrodes else ''),*p) for i,p in enumerate(positions,1)]
        for start in range(0,len(rows),24):
            new_page(); header('Station coordinate checklist','* marks slots selected for this batch. Teach gripping Z after the physical rack is assembled.')
            text(15,30,'Station',4); text(115,30,'X',4); text(165,30,'Y',4); text(215,30,'Tool Z',4)
            for n,(name,x,y,z) in enumerate(rows[start:start+24]):
                ypage=38+n*6.1
                for xpage,value in ((15,name),(115,f'{x:.2f}'),(165,f'{y:.2f}'),(215,f'{z:.2f}')): text(xpage,ypage,value)
                line(15,ypage+1.5,270,ypage+1.5,'#e1e8ed',.15)
        # A4 landscape tiles cover 260 x 155 mm with no overlap. Trim at frame.
        for row in range(rows_count):
            for col in range(cols):
                new_page(); x0=minx+col*tw; y0=miny+row*th
                header(f'Actual-size tile {col+1}/{cols}, {row+1}/{rows_count}',f'100% / Actual size. Trim to frame; tile rows increase in +Y. Lower-left XY: ({x0:g}, {y0:g}).')
                frame=QRectF(15,30,tw,th)
                draw_map(lambda x,y:QPointF(15+x-x0,185-(y-y0)),frame)
                painter.setPen(QPen(QColor('#234452'),.3)); painter.drawRect(frame)
                text(15,193,'Verify this line measures exactly 50 mm:',3); line(105,192,155,192,'#234452',.4)
                line(105,190,105,194,'#234452'); line(155,190,155,194,'#234452')
    finally: painter.end()
    return path
