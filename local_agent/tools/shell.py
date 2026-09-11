from __future__ import annotations

import subprocess

from local_agent.security.policy import check_shell


def execute(command: str, workspace: str, timeout: int = 120) -> dict:
    check_shell(command)
    proc = subprocess.run(
        command,
        shell=True,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }
