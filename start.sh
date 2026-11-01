#!/usr/bin/env bash
# Start the Daeloryn local backend and frontend through their single owner.
# The Python launcher checks both ports, reports readiness and handles Ctrl+C.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Daeloryn requires Python 3.11+ (python3).' >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || [[ ! -f "$ROOT/web/node_modules/vite/bin/vite.js" ]]; then
  printf '%s\n' 'Frontend dependencies not ready. Install Node.js and run:' '  cd web && npm ci' >&2
  exit 1
fi

# Forward additional CLI options (e.g. --repository-root PATH). Do not
# background processes, kill occupied ports, or silently install packages.
exec python3 "$ROOT/scripts/console.py" \
  --enable-copilot-chat \
  --enable-project-picker \
  --enable-patch-apply \
  --open \
  "$@"
