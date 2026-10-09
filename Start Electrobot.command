#!/bin/sh
# Double-click in Finder, or run this script from any directory.
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
if [ -x "$project_dir/.venv/bin/python" ]; then
    "$project_dir/.venv/bin/python" "$project_dir/run_app.py" "$@"
else
    echo 'Create the project virtual environment and install dependencies first.' >&2
    echo 'See README.md for setup instructions.' >&2
    exit 1
fi
launch_status=$?
if [ "$launch_status" -ne 0 ] && [ -t 0 ]; then
    printf 'Press Enter to close this window… '
    read -r response
fi
exit "$launch_status"
