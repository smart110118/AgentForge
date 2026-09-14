#!/usr/bin/env python3
"""Write Cursor / Claude Code / Codex project files that point at mcp-docker.sh."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

SECTION = """## AgentForge

Implementation goes through MCP `local-agent` (`local_agent_execute` / `status` / `result` / `retry` / `cancel`).
Use skill `local-dev` (`/local-dev` or `$local-dev`).
Trust `local_agent_result.status` and test exit code 0, not executor prose.
"""


def _clients() -> set[str]:
    raw = os.environ.get("INSTALL_CLIENTS") or "cursor,claude,codex"
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _mcp_stdio(root: Path, workspace: str) -> dict:
    return {
        "mcpServers": {
            "local-agent": {
                "command": "bash",
                "args": [str(root / "scripts" / "mcp-docker.sh")],
                "env": {"WORKSPACE_FOLDER": workspace},
            }
        }
    }


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _append_section(path: Path) -> None:
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "## AgentForge" in old:
        return
    body = (old.rstrip() + "\n\n" if old.strip() else "") + SECTION
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def install(root: Path, dest: Path, clients: set[str] | None = None) -> None:
    root, dest = root.resolve(), dest.resolve()
    clients = clients if clients is not None else _clients()
    skill = root / "cursor" / "skills" / "local-dev" / "SKILL.md"
    agent = root / "cursor" / "agents" / "local-coder.md"
    mcp_sh = str(root / "scripts" / "mcp-docker.sh")

    if "cursor" in clients:
        cdir = dest / ".cursor"
        (cdir / "skills" / "local-dev").mkdir(parents=True, exist_ok=True)
        (cdir / "agents").mkdir(parents=True, exist_ok=True)
        shutil.copy(skill, cdir / "skills" / "local-dev" / "SKILL.md")
        shutil.copy(agent, cdir / "agents" / "local-coder.md")
        mcp = _mcp_stdio(root, "${workspaceFolder}")
        (cdir / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")
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
        (cdir / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n")

    if "claude" in clients:
        (dest / ".claude" / "skills" / "local-dev").mkdir(parents=True, exist_ok=True)
        (dest / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        shutil.copy(skill, dest / ".claude" / "skills" / "local-dev" / "SKILL.md")
        shutil.copy(agent, dest / ".claude" / "agents" / "local-coder.md")
        mcp = _mcp_stdio(root, str(dest))
        (dest / ".mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")
        _append_section(dest / "CLAUDE.md")

    if "codex" in clients:
        (dest / ".agents" / "skills" / "local-dev").mkdir(parents=True, exist_ok=True)
        (dest / ".codex").mkdir(parents=True, exist_ok=True)
        shutil.copy(skill, dest / ".agents" / "skills" / "local-dev" / "SKILL.md")
        toml = (
            "[mcp_servers.local-agent]\n"
            f"command = {_toml_str('bash')}\n"
            f"args = [{_toml_str(mcp_sh)}]\n"
            "startup_timeout_sec = 30\n"
            "tool_timeout_sec = 600\n"
            "\n"
            "[mcp_servers.local-agent.env]\n"
            f"WORKSPACE_FOLDER = {_toml_str(str(dest))}\n"
        )
        (dest / ".codex" / "config.toml").write_text(toml)
        _append_section(dest / "AGENTS.md")


def main() -> None:
    root = Path(os.environ["ROOT"])
    dest = Path(os.environ["DEST"])
    install(root, dest)
    print(f"wrote client files under {dest.resolve()} ({', '.join(sorted(_clients()))})")


if __name__ == "__main__":
    main()
