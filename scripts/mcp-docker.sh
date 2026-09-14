#!/usr/bin/env bash
# Cursor MCP stdio entry: docker run -i agentforge
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${AGENTFORGE_IMAGE:-agentforge:latest}"
WS="${WORKSPACE_FOLDER:-${PWD}}"
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "image ${IMAGE} missing; run: docker build -t ${IMAGE} ${ROOT}" >&2
  exit 1
fi
ENV_FILE=()
if [[ -f "${ROOT}/.env" ]]; then
  ENV_FILE=(--env-file "${ROOT}/.env")
fi
exec docker run --rm -i \
  "${ENV_FILE[@]}" \
  -v "${ROOT}/configs:/app/configs:ro" \
  -v "${WS}:${WS}" \
  "${IMAGE}" --mcp
