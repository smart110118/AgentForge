#!/usr/bin/env bash
# One-shot: [2] Gateway image + [1] Cursor files. Does not install the local model.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT}"
IMAGE="${AGENTFORGE_IMAGE:-agentforge:latest}"

chmod +x "${ROOT}/scripts/"*.sh "${ROOT}/cursor/hooks/gate.py"

if ! command -v docker >/dev/null 2>&1; then
  echo "need docker" >&2
  exit 1
fi

echo "==> [2] Gateway  docker build -t ${IMAGE}"
docker build -t "${IMAGE}" "${ROOT}"

echo "==> [1] Cursor   install into ${DEST}"
mkdir -p "${DEST}/.cursor/skills/local-dev" "${DEST}/.cursor/agents"
cp "${ROOT}/cursor/skills/local-dev/SKILL.md" "${DEST}/.cursor/skills/local-dev/SKILL.md"
cp "${ROOT}/cursor/agents/local-coder.md" "${DEST}/.cursor/agents/local-coder.md"

ROOT="${ROOT}" DEST="${DEST}" python3 - <<'PY'
import json, os
from pathlib import Path

root = Path(os.environ["ROOT"]).resolve()
dest = Path(os.environ["DEST"]).resolve() / ".cursor"
dest.mkdir(parents=True, exist_ok=True)

mcp = {
    "mcpServers": {
        "local-agent": {
            "command": "bash",
            "args": [str(root / "scripts" / "mcp-docker.sh")],
            "env": {"WORKSPACE_FOLDER": "${workspaceFolder}"},
        }
    }
}
(dest / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")

hooks = {
    "version": 1,
    "hooks": {
        "subagentStop": [
            {
                "command": str(root / "cursor" / "hooks" / "gate.py"),
                "timeout": 60,
                "loop_limit": 1,
            }
        ]
    },
}
(dest / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n")
print(f"wrote {dest / 'mcp.json'}")
print(f"wrote {dest / 'hooks.json'}")
PY

echo
echo "安装完成（未部署本地模型）。"
echo "  [1] Cursor:  打开 ${DEST} → Settings → MCP → 打开 local-agent（绿灯）"
echo "  [2] Gateway: 镜像 ${IMAGE}，由 Cursor MCP 按需 docker run，不必常驻"
echo "  [3] 模型:    配置 LOCAL_AGENT_ENDPOINT 后执行 ${ROOT}/scripts/healthcheck.sh"
echo
echo "装到其他仓库:  ${ROOT}/scripts/install.sh /abs/path/to/your-project"
