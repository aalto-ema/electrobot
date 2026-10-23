"""Generate the photo-informed cap and compatible compact contact insert."""
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from electrobot.robot_cell_cap import export
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    d=json.loads((HERE/'dimensions.json').read_text())
    contact=json.loads((HERE.parent/'fixed-contact-prototype/dimensions.json').read_text())
    contact['insert_flange_od']=d['compact_insert_flange_diameter']
    # Remove only managed gauge outputs whose names change with configuration.
    for pattern in ('glass_thread_gauge_*.stl','fitting_thread_gauge_*.stl'):
        for path in HERE.glob(pattern): path.unlink()
    result=export(d,contact,HERE)
    from preview import preview,layout
    preview(d,contact,HERE)
    layout(d,HERE)
    archive=HERE.parent/'robot-cell-cap-print-files.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(HERE.iterdir()):
            if path.is_file() and (path.suffix in ('.stl','.json','.png','.svg') or path.name=='README.md'):
                bundle.write(path,arcname=f'robot-cell-cap/{path.name}')
    print(json.dumps({'geometry_id':result['geometry_id'],'interfaces':result['interfaces'],'plate_bounds_mm':result['plate_bounds_mm']},indent=2))
