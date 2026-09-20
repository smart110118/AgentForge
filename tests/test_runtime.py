from __future__ import annotations

import json
import subprocess
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

    def test_snapshot_keeps_allow_not_whole_tree(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "noise.py").write_text("n\n")
            rec = TaskManager().create(
                {
                    "task_id": "t-allow",
                    "workspace": d,
                    "objective": "add hello()",
                    "files": {"allow": ["hello.py"]},
                    "execution": {"max_iterations": 3},
                }
            )
            run_task(rec, client=FakeClient())
            self.assertEqual(rec.files_changed, ["hello.py"])
            self.assertNotIn("noise.py", rec.files_changed)

    def test_green_tests_without_writes_is_not_success(self):
        class Noop:
            def chat(self, messages, tools=None, temperature=0.2):
                return {"choices": [{"message": {"content": "already done"}}]}

        with tempfile.TemporaryDirectory() as d:
            rec = TaskManager().create(
                {
                    "task_id": "t-noop",
                    "workspace": d,
                    "objective": "implement",
                    "test": {"command": "python3 -c 'raise SystemExit(0)'"},
                    "execution": {"max_iterations": 2},
                }
            )
            run_task(rec, client=Noop())
            self.assertEqual(rec.status.value, "failed")
            self.assertFalse(rec.files_changed)


    def test_preexisting_head_dirt_is_not_success(self):
        class Noop:
            def chat(self, messages, tools=None, temperature=0.2):
                return {"choices": [{"message": {"content": "already done"}}]}

        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("old\n")
            subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "a.py"],
                cwd=d,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
                cwd=d,
                check=True,
                capture_output=True,
            )
            Path(d, "a.py").write_text("polling\n")
            rec = TaskManager().create(
                {
                    "task_id": "t-dirty",
                    "workspace": d,
                    "objective": "add hook, not polling",
                    "files": {"allow": ["a.py"]},
                    "execution": {"max_iterations": 2},
                }
            )
            run_task(rec, client=Noop())
            self.assertEqual(rec.status.value, "failed")
            self.assertFalse(rec.files_changed)
            self.assertEqual(rec.diff_summary, "(no diff)")

    def test_replay_same_patch_stalls_before_max_iter(self):
        class Replay:
            def chat(self, messages, tools=None, temperature=0.2):
                body = {"name": "patch_file", "path": "a.py", "old": "old\n", "new": "polling\n"}
                return {"choices": [{"message": {"content": json.dumps(body)}}]}

        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("old\n")
            subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "a.py"],
                cwd=d,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
                cwd=d,
                check=True,
                capture_output=True,
            )
            rec = TaskManager().create(
                {
                    "task_id": "t-replay",
                    "workspace": d,
                    "objective": "add hook",
                    "files": {"allow": ["a.py"]},
                    "test": {"command": "python3 -c 'raise SystemExit(1)'"},
                    "execution": {"max_iterations": 8},
                }
            )
            run_task(rec, client=Replay())
            self.assertEqual(rec.status.value, "failed")
            self.assertLess(rec.iteration, 8)
            self.assertIn("stalled", rec.error)
            self.assertEqual(Path(d, "a.py").read_text(), "polling\n")


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
