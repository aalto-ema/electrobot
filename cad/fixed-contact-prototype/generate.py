"""Regenerate the standalone fixed-contact test kit from repository root."""
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from electrobot.fixed_contact_cad import export

HERE = Path(__file__).resolve().parent
if __name__ == '__main__':
    dimensions = json.loads((HERE/'dimensions.json').read_text())
    manifest = export(dimensions, HERE)
    from preview import preview
    preview(dimensions, HERE)
    archive = HERE.parent/'fixed-contact-prototype-print-files.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(HERE.iterdir()):
            if path.is_file() and (path.suffix in ('.stl', '.json', '.png') or path.name == 'README.md'):
                bundle.write(path, arcname=f'fixed-contact-prototype/{path.name}')
    print(json.dumps({'geometry_id': manifest['geometry_id'], 'parts': len(manifest['parts']),
                      'interfaces': manifest['interfaces'], 'plate_bounds_mm': manifest['plate_bounds_mm'],
                      'print_archive': archive.name}, indent=2))
