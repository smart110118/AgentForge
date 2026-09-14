from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_agent.mcp.tools import execute
from local_agent.tasks.dag import toposort


class SeqClient:
    def __init__(self, path: str, body: str) -> None:
        self.path = path
        self.body = body
        self.n = 0

    def chat(self, messages, tools=None, temperature=0.2):
        self.n += 1
        if self.n == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"name": "write_file", "path": self.path, "content": self.body}
                            )
                        }
                    }
                ]
            }
        return {
            "choices": [
                {"message": {"content": json.dumps({"name": "finish", "summary": self.path})}}
            ]
        }


class DagTest(unittest.TestCase):
    def test_cycle(self):
        with self.assertRaises(ValueError):
            toposort(
                [
                    {"task_id": "a", "depends_on": ["b"], "objective": "a"},
                    {"task_id": "b", "depends_on": ["a"], "objective": "b"},
                ]
            )

    def test_order_t1_t2(self):
        order = toposort(
            [
                {"task_id": "T2", "depends_on": ["T1"], "objective": "2"},
                {"task_id": "T1", "depends_on": [], "objective": "1"},
            ]
        )
        self.assertEqual([x["task_id"] for x in order], ["T1", "T2"])

    def test_execute_dag(self):
        from local_agent.agent import runtime as rt

        with tempfile.TemporaryDirectory() as d:
            orig = rt.qwen_client

            def fake_client(cfg=None):
                # each run_task gets a new client; distinguish by existing files
                if not (Path(d) / "a.py").exists():
                    return SeqClient("a.py", "a=1\n")
                return SeqClient("b.py", "b=1\n")

            rt.qwen_client = fake_client  # type: ignore
            try:
                out = execute(
                    {
                        "task_id": "parent",
                        "workspace": d,
                        "objective": "dag",
                        "dag": {
                            "parallel": 1,
                            "tasks": [
                                {"task_id": "T1", "objective": "write a"},
                                {"task_id": "T2", "objective": "write b", "depends_on": ["T1"]},
                            ],
                        },
                        "execution": {"max_iterations": 3},
                    }
                )
            finally:
                rt.qwen_client = orig
            self.assertEqual(out["status"], "success")
            self.assertEqual([x["task_id"] for x in out["dag"]], ["T1", "T2"])
            self.assertTrue((Path(d) / "a.py").is_file())
            self.assertTrue((Path(d) / "b.py").is_file())


if __name__ == "__main__":
    unittest.main()
