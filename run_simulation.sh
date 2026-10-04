#!/bin/sh
set -eu
cd "$(dirname "$0")"
export UV_CACHE_DIR=/private/tmp/lerobot-uv-cache
export UV_PYTHON_INSTALL_DIR=/private/tmp/lerobot-python
export MPLCONFIGDIR=/private/tmp/lerobot-mpl
export PYTHONDONTWRITEBYTECODE=1
sim_python=/private/tmp/rx-dev-lerobot-venv/bin/python
if [ ! -x "$sim_python" ]; then
    uv venv --python 3.12 /private/tmp/rx-dev-lerobot-venv
fi
if "$sim_python" -c 'from importlib.metadata import version; version("opencv-python")' 2>/dev/null; then
    uv pip uninstall --python "$sim_python" opencv-python opencv-python-headless
fi
uv pip install --python "$sim_python" --excludes excludes-lerobot.txt -r requirements-lerobot.txt
if [ "${1:-}" = "serve" ]; then
    shift
    exec "$sim_python" -u -m backend.server "$@"
elif [ "${1:-}" = "agent" ]; then
    shift
    exec "$sim_python" -u -m backend.pusht_agent "$@"
else
    exec "$sim_python" -u -m backend.simulation "$@"
fi
