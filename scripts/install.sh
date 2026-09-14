#!/usr/bin/env bash
# One-shot: [2] Gateway image + [1] online-brain client files. Does not install the executor model.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT}"
IMAGE="${AGENTFORGE_IMAGE:-agentforge:latest}"

chmod +x "${ROOT}/scripts/"*.sh "${ROOT}/cursor/hooks/gate.py" "${ROOT}/scripts/install_clients.py"

if [[ "${INSTALL_SKIP_DOCKER:-}" != "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "need docker" >&2
    exit 1
  fi
  echo "==> [2] Gateway  docker build -t ${IMAGE}"
  docker build -t "${IMAGE}" "${ROOT}"
else
  echo "==> [2] Gateway  skip docker (INSTALL_SKIP_DOCKER=1)"
fi

echo "==> [1] Clients  install into ${DEST}  (${INSTALL_CLIENTS:-cursor,claude,codex})"
ROOT="${ROOT}" DEST="${DEST}" python3 "${ROOT}/scripts/install_clients.py"

echo
echo "安装完成（未部署执行模型）。一个镜像 ${IMAGE}，三个终端共用 mcp-docker.sh。"
echo "  Cursor:      打开 ${DEST} → Settings → MCP → 打开 local-agent"
echo "  Claude Code: 在 ${DEST} 运行 claude，批准项目 .mcp.json"
echo "  Codex:       信任该项目后用 .codex/config.toml；/mcp 可能只列全局，agent 仍能调项目 MCP"
echo "  Gateway:     由各终端 MCP 按需 docker run，不必常驻"
echo "  模型:        配置 .env 后执行 ${ROOT}/scripts/healthcheck.sh"
echo
echo "装到其他仓库:  ${ROOT}/scripts/install.sh /abs/path/to/your-project"
echo "只要部分客户端: INSTALL_CLIENTS=cursor,claude ${ROOT}/scripts/install.sh /abs/path"
