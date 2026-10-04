#!/bin/sh
set -eu
cd "$(dirname "$0")"
sh run_simulation.sh serve &
backend_pid=$!
frontend_pid=""
cleanup() {
    kill "$backend_pid" 2>/dev/null || true
    if [ -n "$frontend_pid" ]; then kill "$frontend_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM
python3 -m http.server 3030 --bind 127.0.0.1 --directory frontend &
frontend_pid=$!
echo 'Frontend: http://127.0.0.1:3030'
echo 'Backend:  http://127.0.0.1:8787/api/health'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
    sleep 1
done
echo 'A server stopped. Shutting down the companion server.' >&2
exit 1
