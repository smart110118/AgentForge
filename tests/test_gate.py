from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_agent.tools.shell import execute
from local_agent.tools.tests import run_gate, run_tests


class GateTest(unittest.TestCase):
    def test_failed_test_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "fail.py").write_text("import sys; sys.exit(1)\n")
            out = run_tests("python3 fail.py", d)
            self.assertFalse(out["success"])
            self.assertEqual(out["exit_code"], 1)
            gate = run_gate(d, "python3 fail.py")
            self.assertFalse(gate["ok"])

    def test_pass_test(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "ok.py").write_text("print('ok')\n")
            gate = run_gate(d, "python3 ok.py")
            self.assertTrue(gate["ok"])

    def test_shell_returns_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            r = execute("python3 -c 'print(1)'", d)
            self.assertEqual(r["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
