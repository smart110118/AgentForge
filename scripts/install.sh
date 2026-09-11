#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3.11 -m pip install -e "${ROOT}[dev]"
chmod +x "${ROOT}/scripts/"*.sh
