#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi
MODEL="${LLAMA_MODEL:-/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf}"
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8000}"
CTX="${LLAMA_CTX:-16384}"
if [[ ! -f "${MODEL}" ]]; then
  echo "GGUF not found: ${MODEL}" >&2
  echo "Set LLAMA_MODEL in .env (see .env.example)." >&2
  exit 1
fi
exec llama-server -m "${MODEL}" --host "${HOST}" --port "${PORT}" -c "${CTX}"
