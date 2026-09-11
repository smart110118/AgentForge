from __future__ import annotations

import unittest

from local_agent.mcp.server import TOOL_LIST, _handle
from local_agent.mcp.tools import status


class McpTest(unittest.TestCase):
    def test_initialize_and_tools(self):
        init = _handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "local-agent")
        listed = _handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in listed["result"]["tools"]]
        self.assertEqual(names, [t["name"] for t in TOOL_LIST])
        self.assertIn("local_agent_execute", names)
        self.assertIn("local_agent_retry", names)

    def test_unknown_status(self):
        self.assertEqual(status("nope")["error"], "unknown task_id")


if __name__ == "__main__":
    unittest.main()
