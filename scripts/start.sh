#!/usr/bin/env bash
# Optional: only if you start llama-server on this machine.
# Default executor is the remote server in configs/models.yaml (192.168.7.182:18080).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi
MODEL="${LLAMA_MODEL:-}"
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8000}"
CTX="${LLAMA_CTX:-65536}"
if [[ -z "${MODEL}" || ! -f "${MODEL}" ]]; then
  echo "Remote llama.cpp is configured at http://192.168.7.182:18080" >&2
  echo "To start a local server, set LLAMA_MODEL to a GGUF path." >&2
  exit 1
fi
exec llama-server -m "${MODEL}" --host "${HOST}" --port "${PORT}" -c "${CTX}"
