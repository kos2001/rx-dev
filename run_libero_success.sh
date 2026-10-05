#!/bin/sh
# Run the pinned, already-trained drawer policy locally; do not train or call providers.
set -eu
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ]; then
  echo 'This experimental setup is pinned for macOS. Use the official LeRobot LIBERO setup on Linux.' >&2
  exit 1
fi
LIBERO_POLICY_VENV=${LIBERO_POLICY_VENV:-/private/tmp/rx-dev-libero-macos-venv}
export UV_CACHE_DIR=${UV_CACHE_DIR:-/private/tmp/lerobot-uv-cache}
export UV_PYTHON_INSTALL_DIR=${UV_PYTHON_INSTALL_DIR:-/private/tmp/lerobot-python}
if [ ! -x "$LIBERO_POLICY_VENV/bin/python" ]; then
  uv venv --python 3.12 "$LIBERO_POLICY_VENV"
fi
# Experimental pinned environment omits Linux EGL probes and keeps NumPy 1.26
# for robosuite 1.4. Never install this into the main LeRobot application venv.
uv pip install --python "$LIBERO_POLICY_VENV/bin/python" --no-deps -r requirements/libero-act-macos.txt
exec "$LIBERO_POLICY_VENV/bin/python" -m backend.libero_success "$@"
