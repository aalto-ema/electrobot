"""Run from repository root: .venv/bin/python cad/electrode-holder/generate.py"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from electrobot.electrode_holder import export_holder
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    from schematic import schematic
    from preview import preview
    d=json.loads((HERE/'dimensions.json').read_text())
    manifest=export_holder(d,HERE)
    schematic(d,HERE); preview(d,HERE)
    print(json.dumps(manifest,indent=2))
