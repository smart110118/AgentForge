#!/usr/bin/env bash
set -euo pipefail
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8000}"
BASE="http://${HOST}:${PORT}"
if curl -sf "${BASE}/v1/models" >/dev/null; then
  exit 0
fi
if curl -sf "${BASE}/health" >/dev/null; then
  exit 0
fi
echo "llama-server not healthy at ${BASE}" >&2
exit 1
