from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_install():
    p = Path(__file__).resolve().parents[1] / "scripts" / "install_clients.py"
    spec = importlib.util.spec_from_file_location("install_clients", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.install


install = _load_install()


class InstallClientsTest(unittest.TestCase):
    def test_all_clients_point_at_same_mcp(self):
        root = Path(__file__).resolve().parents[1]
        mcp = str(root / "scripts" / "mcp-docker.sh")
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            install(root, dest, {"cursor", "claude", "codex"})
            cursor = json.loads((dest / ".cursor" / "mcp.json").read_text())
            claude = json.loads((dest / ".mcp.json").read_text())
            self.assertEqual(cursor["mcpServers"]["local-agent"]["args"][0], mcp)
            self.assertEqual(claude["mcpServers"]["local-agent"]["args"][0], mcp)
            self.assertEqual(cursor["mcpServers"]["local-agent"]["env"]["WORKSPACE_FOLDER"], "${workspaceFolder}")
            self.assertEqual(claude["mcpServers"]["local-agent"]["env"]["WORKSPACE_FOLDER"], str(dest.resolve()))
            toml = (dest / ".codex" / "config.toml").read_text()
            self.assertIn("local-agent", toml)
            self.assertIn(mcp, toml)
            self.assertIn("tool_timeout_sec = 600", toml)
            self.assertTrue((dest / ".cursor" / "skills" / "local-dev" / "SKILL.md").is_file())
            self.assertTrue((dest / ".claude" / "skills" / "local-dev" / "SKILL.md").is_file())
            self.assertTrue((dest / ".claude" / "agents" / "local-coder.md").is_file())
            self.assertTrue((dest / ".agents" / "skills" / "local-dev" / "SKILL.md").is_file())
            self.assertIn("## AgentForge", (dest / "CLAUDE.md").read_text())
            self.assertIn("## AgentForge", (dest / "AGENTS.md").read_text())

    def test_append_not_overwrite(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            (dest / "AGENTS.md").write_text("# Existing\nkeep me\n")
            install(root, dest, {"codex"})
            text = (dest / "AGENTS.md").read_text()
            self.assertIn("keep me", text)
            self.assertIn("## AgentForge", text)
            install(root, dest, {"codex"})
            self.assertEqual(text.count("## AgentForge"), 1)

    def test_cursor_only(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            install(root, dest, {"cursor"})
            self.assertTrue((dest / ".cursor" / "mcp.json").is_file())
            self.assertFalse((dest / ".mcp.json").exists())
            self.assertFalse((dest / ".codex" / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
