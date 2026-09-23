"""Snapshot Engine: captures atomic workspace state, git diffs, and runtime metadata."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from local_agent.tools import git


@dataclass
class RuntimeSnapshot:
    workspace_path: str
    git_head: str = ""
    git_status: str = ""
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    git_diff: str = ""
    python_version: str = field(default_factory=platform.python_version)
    os_info: str = field(default_factory=lambda: f"{platform.system()} {platform.release()}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SnapshotEngine:
    """Takes immutable snapshots of code workspace, git trees, diffs, and runtime info."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = str(Path(workspace).resolve())

    def _run_git(self, *args: str) -> str:
        try:
            res = subprocess.run(
                ["git", "-C", self.workspace, *args],
                capture_output=True,
                text=True,
                check=False,
            )
            return (res.stdout or res.stderr).strip()
        except Exception:
            return ""

    def capture(self, max_diff_chars: int = 10_000) -> RuntimeSnapshot:
        """Capture the full atomic snapshot of the workspace."""
        head_commit = self._run_git("rev-parse", "HEAD") or "unknown"
        status_raw = self._run_git("status", "--porcelain")

        modified_files: list[str] = []
        untracked_files: list[str] = []

        for line in status_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            status_code = line[:2]
            filepath = line[3:].strip()
            if "??" in status_code:
                untracked_files.append(filepath)
            else:
                modified_files.append(filepath)

        diff_raw = self._run_git("diff", "HEAD")
        if not diff_raw:
            # Check unstaged diff if HEAD diff was empty
            diff_raw = self._run_git("diff")

        if len(diff_raw) > max_diff_chars:
            half = max_diff_chars // 2
            diff_raw = (
                diff_raw[:half]
                + f"\n\n[... Diff truncated ({len(diff_raw) - max_diff_chars} chars) ...]\n\n"
                + diff_raw[-half:]
            )

        return RuntimeSnapshot(
            workspace_path=self.workspace,
            git_head=head_commit,
            git_status=status_raw,
            modified_files=modified_files,
            untracked_files=untracked_files,
            git_diff=diff_raw,
        )
