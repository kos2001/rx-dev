#!/bin/sh
# Experimental macOS smoke runner. It does not train or evaluate a learned policy.
set -eu
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ]; then
  echo 'This experimental setup is pinned for macOS. Use the official LeRobot LIBERO setup on Linux.' >&2
  exit 1
fi
LIBERO_PROBE_VENV=${LIBERO_PROBE_VENV:-/private/tmp/rx-dev-libero-macos-venv}
export UV_CACHE_DIR=${UV_CACHE_DIR:-/private/tmp/lerobot-uv-cache}
export UV_PYTHON_INSTALL_DIR=${UV_PYTHON_INSTALL_DIR:-/private/tmp/lerobot-python}
if [ ! -x "$LIBERO_PROBE_VENV/bin/python" ]; then
  uv venv --python 3.12 "$LIBERO_PROBE_VENV"
fi
# Linux EGL discovery libraries are deliberately omitted. The probe uses the
# existing robosuite macOS GLFW/CGL path. Never apply this to the main app venv.
uv pip install --python "$LIBERO_PROBE_VENV/bin/python" --no-deps -r requirements/libero-macos.txt
exec "$LIBERO_PROBE_VENV/bin/python" -m backend.libero_probe "$@"
