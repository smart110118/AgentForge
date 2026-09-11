from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.security.policy import PolicyError, check_shell
from local_agent.security.sandbox import SandboxError, resolve_in_workspace
from local_agent.tasks.schema import parse_task
from local_agent.tools.filesystem import patch_file, write_file


class SchemaTest(unittest.TestCase):
    def test_missing_objective(self):
        with self.assertRaises(ValueError):
            parse_task({"task_id": "t", "workspace": "/tmp"})


class SandboxTest(unittest.TestCase):
    def test_rejects_outside(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SandboxError):
                resolve_in_workspace(d, "../secret")


class PolicyTest(unittest.TestCase):
    def test_allow_pytest(self):
        check_shell("pytest tests/auth")

    def test_block_rm(self):
        with self.assertRaises(PolicyError):
            check_shell("rm -rf /")

    def test_block_sudo(self):
        with self.assertRaises(PolicyError):
            check_shell("sudo pytest")


class FsTest(unittest.TestCase):
    def test_write_and_patch(self):
        with tempfile.TemporaryDirectory() as d:
            write_file(d, "a.py", "x = 1\n", ["**/*"])
            patch_file(d, "a.py", "x = 1", "x = 2", ["**/*"])
            self.assertEqual(Path(d, "a.py").read_text(), "x = 2\n")

    def test_allow_glob(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SandboxError):
                write_file(d, "other.py", "x", ["src/**"])


if __name__ == "__main__":
    unittest.main()
