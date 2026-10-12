#!/usr/bin/env python3
"""Run project checks using .venv when present; no physical devices are used."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit-only',action='store_true',help='Skip the two UI checks and screenshot regeneration')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    local=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    interpreter=str(local) if local.is_file() else sys.executable
    environment=os.environ.copy(); environment['QT_QPA_PLATFORM']='offscreen'
    checks=[('Unit tests',['-m','unittest','discover','-s','tests','-v'])]
    if not args.unit_only:
        checks.extend([('Simulation UI',['tests/ui_smoke.py']),('Hardware UI with mock devices',['tests/hardware_ui_smoke.py'])])
        print('UI checks refresh screenshots in cad/; inspect their changes before committing.',flush=True)
    for name,arguments in checks:
        print(f'\nRunning {name} with {interpreter}',flush=True)
        result=subprocess.run([interpreter,*arguments],cwd=root,env=environment,check=False)
        if result.returncode:
            print(f'{name} failed (exit {result.returncode}).',file=sys.stderr)
            return result.returncode if result.returncode>0 else 1
    print('\nAll requested checks passed. No physical hardware was used.',flush=True)
    return 0


if __name__=='__main__':
    sys.exit(main())
