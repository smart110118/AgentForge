from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_agent.agent.runtime import parse_actions, run_task
from local_agent.tasks.manager import TaskManager
from local_agent.tasks.schema import parse_task


class FakeClient:
    def __init__(self) -> None:
        self.n = 0

    def chat(self, messages, tools=None, temperature=0.2):
        self.n += 1
        if self.n == 1:
            body = {
                "name": "write_file",
                "path": "hello.py",
                "content": "def hello():\n    return 'ok'\n",
            }
            return {"choices": [{"message": {"content": json.dumps(body)}}]}
        return {
            "choices": [
                {"message": {"content": json.dumps({"name": "finish", "summary": "added hello"})}}
            ]
        }


class ParseTest(unittest.TestCase):
    def test_json_action(self):
        acts = parse_actions('{"name":"write_file","path":"a.py","content":"x"}')
        self.assertEqual(acts[0]["name"], "write_file")
        self.assertEqual(acts[0]["arguments"]["path"], "a.py")


class RuntimeTest(unittest.TestCase):
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            rec = TaskManager().create(
                {
                    "task_id": "t-hello",
                    "workspace": d,
                    "objective": "add hello()",
                    "execution": {"max_iterations": 3},
                }
            )
            run_task(rec, client=FakeClient())
            self.assertEqual(rec.status.value, "success")
            self.assertTrue((Path(d) / "hello.py").is_file())


class McpApiTest(unittest.TestCase):
    def test_schema_via_parse(self):
        t = parse_task(
            {
                "task_id": "task-1",
                "workspace": "/tmp",
                "objective": "x",
                "acceptance": ["y"],
                "test": {"command": "pytest tests/auth"},
                "execution": {"max_iterations": 8},
            }
        )
        self.assertEqual(t.test_command, "pytest tests/auth")


if __name__ == "__main__":
    unittest.main()
