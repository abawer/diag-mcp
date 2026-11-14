#!/usr/bin/env bash
# Day-1 dev launcher: run the MCP server without Docker (no daemon needed).
# Dependencies live in repo-local .deps (pip install --target .deps -r requirements.txt).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .deps ]; then
  pip install -q --target .deps -r requirements.txt
fi

export PYTHONPATH="$PWD/.deps${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m mcp_server.server
