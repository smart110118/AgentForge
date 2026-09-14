#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi
PROVIDER="${LLM_PROVIDER:-local}"
auth=()
case "${PROVIDER}" in
  xai)
    ENDPOINT="${XAI_BASE_URL:-https://api.x.ai/v1}"
    KEY="${XAI_API_KEY:-}"
    ;;
  openai)
    ENDPOINT="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
    KEY="${OPENAI_API_KEY:-}"
    ;;
  *)
    ENDPOINT="${LOCAL_AGENT_ENDPOINT:-http://192.168.7.182:18080/v1}"
    KEY=""
    ;;
esac
ENDPOINT="${ENDPOINT%/}"
if [[ -n "${KEY}" ]]; then
  auth=(-H "Authorization: Bearer ${KEY}")
fi
if curl -sf "${auth[@]}" "${ENDPOINT}/models" >/dev/null; then
  exit 0
fi
BASE="${ENDPOINT%/v1}"
BASE="${BASE%/}"
if [[ "${PROVIDER}" == "local" ]] && curl -sf "${BASE}/health" >/dev/null; then
  exit 0
fi
if curl -sf "${auth[@]}" "${BASE}/models" >/dev/null; then
  exit 0
fi
echo "executor not healthy provider=${PROVIDER} endpoint=${ENDPOINT}" >&2
exit 1
