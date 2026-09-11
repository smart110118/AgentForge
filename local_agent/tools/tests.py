from __future__ import annotations

from local_agent.tools import git as git_tools
from local_agent.tools.shell import execute


def run_tests(command: str, workspace: str, timeout: int = 180) -> dict:
    result = execute(command, workspace, timeout=timeout)
    passed = failed = 0
    out = result["stdout"] + result["stderr"]
    # ponytail: parse nothing fancy; gate uses exit_code only
    if result["exit_code"] == 0:
        passed = 1
    else:
        failed = 1
    return {
        "exit_code": result["exit_code"],
        "passed": passed,
        "failed": failed,
        "output": out[-8000:],
        "success": result["exit_code"] == 0,
    }


def run_gate(workspace: str, test_command: str | None) -> dict:
    check = git_tools.diff_check(workspace)
    tests = None
    if test_command:
        tests = run_tests(test_command, workspace)
    ok = bool(check["ok"]) and (tests is None or tests["success"])
    return {"ok": ok, "git_diff_check": check, "tests": tests}
