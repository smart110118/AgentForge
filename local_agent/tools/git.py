from __future__ import annotations

import subprocess
from pathlib import Path


def _git(workspace: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True,
        text=True,
    )


def status(workspace: str) -> str:
    p = _git(workspace, "status", "--porcelain")
    return (p.stdout or p.stderr).strip() or "(clean)"


def diff(workspace: str, paths: list[str] | None = None) -> str:
    args = ["diff", "HEAD"]
    if paths:
        args += ["--", *paths]
    p = _git(workspace, *args)
    text = p.stdout.strip()
    if not text:
        args[0:1] = ["diff"]
        p = _git(workspace, *args)
        text = p.stdout.strip()
    return text[:20000] or "(no diff)"


def log(workspace: str, n: int = 5) -> str:
    p = _git(workspace, "log", f"-{n}", "--oneline")
    return (p.stdout or p.stderr).strip() or "(no log)"


def changed_files(workspace: str) -> list[str]:
    p = _git(workspace, "status", "--porcelain")
    files: list[str] = []
    for line in p.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def diff_check(workspace: str) -> dict:
    if not (Path(workspace) / ".git").exists():
        return {"ok": True, "output": "not a git repo"}
    p = _git(workspace, "diff", "--check")
    return {"ok": p.returncode == 0, "output": (p.stdout + p.stderr)[-4000:]}
