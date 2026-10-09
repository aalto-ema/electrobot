#!/usr/bin/env python3
"""Launch Electrobot, preferring this project's virtual environment."""
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent
    environment = root / '.venv'
    interpreter = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if interpreter.is_file() and Path(sys.prefix).resolve() != environment.resolve():
        os.execv(str(interpreter), [str(interpreter), str(root / 'run_app.py'), *sys.argv[1:]])
    os.chdir(root)
    try:
        from electrobot.app import main as start_app
    except ModuleNotFoundError as exc:
        print(f'Cannot start Electrobot: missing dependency {exc.name}.', file=sys.stderr)
        print('Install dependencies with: python -m pip install -r requirements.txt', file=sys.stderr)
        return 1
    start_app()
    return 0


if __name__ == '__main__':
    sys.exit(main())
