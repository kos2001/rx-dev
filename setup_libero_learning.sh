#!/bin/sh
# Install only the separate pinned experimental macOS worker.
set -eu
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ]; then
  echo 'Use the official Linux LeRobot LIBERO setup and set RX_LIBERO_PYTHON.' >&2
  exit 1
fi
LIBERO_POLICY_VENV=${LIBERO_POLICY_VENV:-/private/tmp/rx-dev-libero-macos-venv}
export UV_CACHE_DIR=${UV_CACHE_DIR:-/private/tmp/lerobot-uv-cache}
export UV_PYTHON_INSTALL_DIR=${UV_PYTHON_INSTALL_DIR:-/private/tmp/lerobot-python}
if [ ! -x "$LIBERO_POLICY_VENV/bin/python" ]; then
  uv venv --python 3.12 "$LIBERO_POLICY_VENV"
fi
uv pip install --python "$LIBERO_POLICY_VENV/bin/python" --no-deps -r requirements/libero-act-macos.txt
"$LIBERO_POLICY_VENV/bin/python" -c 'import torch, lerobot; print("LIBERO learning worker ready")'
