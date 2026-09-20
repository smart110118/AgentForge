from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from local_agent.tools import git as git_tools


def _init_repo(d: str) -> None:
    subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
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


class GitBaselineTest(unittest.TestCase):
    def test_session_diff_ignores_preexisting_head_dirt(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("old\n")
            _init_repo(d)
            Path(d, "a.py").write_text("polling\n")
            idx = git_tools.capture_baseline(d)
            self.assertTrue(idx)
            try:
                head = git_tools.diff(d)
                self.assertIn("polling", head)
                self.assertIn("-old", head)
                session = git_tools.diff(d, baseline_index=idx)
                self.assertEqual(session, "(no diff)")
                self.assertEqual(git_tools.changed_files(d, baseline_index=idx), [])
                Path(d, "a.py").write_text("polling\nhook\n")
                session = git_tools.diff(d, baseline_index=idx)
                self.assertIn("hook", session)
                self.assertNotIn("-old", session)
                self.assertEqual(git_tools.changed_files(d, baseline_index=idx), ["a.py"])
            finally:
                git_tools.drop_baseline(idx)

    def test_session_diff_includes_new_file(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("old\n")
            _init_repo(d)
            idx = git_tools.capture_baseline(d)
            try:
                Path(d, "b.py").write_text("new\n")
                session = git_tools.diff(d, baseline_index=idx)
                self.assertIn("b.py", session)
                self.assertIn("new", session)
                self.assertIn("b.py", git_tools.changed_files(d, baseline_index=idx))
            finally:
                git_tools.drop_baseline(idx)

    def test_context_omits_head_dirt(self):
        from local_agent.context.manager import build
        from local_agent.tasks.schema import parse_task

        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("old\n")
            _init_repo(d)
            Path(d, "a.py").write_text("polling\n")
            idx = git_tools.capture_baseline(d)
            try:
                task = parse_task(
                    {
                        "task_id": "t",
                        "workspace": d,
                        "objective": "add hook",
                        "files": {"allow": ["a.py"]},
                    }
                )
                text = build(task, baseline_index=idx or "")
                self.assertIn("polling", text)
                self.assertNotIn("-old", text)
                self.assertNotIn("\n--- a/", text)
                self.assertNotIn("# Git diff", text)
            finally:
                git_tools.drop_baseline(idx)


if __name__ == "__main__":
    unittest.main()
