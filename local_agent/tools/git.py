from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def _git(
    workspace: str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _index_env(baseline_index: str | None) -> dict[str, str] | None:
    if not baseline_index:
        return None
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = baseline_index
    return env


def capture_baseline(workspace: str) -> str | None:
    if not (Path(workspace) / ".git").exists():
        return None
    fd, path = tempfile.mkstemp(prefix="af-gitidx-")
    os.close(fd)
    env = _index_env(path)
    _git(workspace, "read-tree", "HEAD", env=env)
    p = _git(workspace, "add", "-A", env=env)
    if p.returncode != 0:
        drop_baseline(path)
        return None
    return path


def drop_baseline(path: str | None) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except OSError:
        pass


def status(workspace: str, baseline_index: str | None = None) -> str:
    if not baseline_index:
        p = _git(workspace, "status", "--porcelain")
        return (p.stdout or p.stderr).strip() or "(clean)"
    env = _index_env(baseline_index)
    lines: list[str] = []
    p = _git(workspace, "diff", "--name-status", env=env)
    for raw in p.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        code, path = raw.split("\t", 1) if "\t" in raw else (raw[0], raw[1:].strip())
        mark = {"M": " M", "A": "??", "D": " D"}.get(code[:1], " M")
        lines.append(f"{mark} {path}")
    others = _git(workspace, "ls-files", "--others", "--exclude-standard", env=env)
    for rel in others.stdout.splitlines():
        rel = rel.strip()
        if rel:
            lines.append(f"?? {rel}")
    return "\n".join(lines) or "(clean)"


def _untracked_diff(workspace: str, rel: str) -> str:
    p = _git(workspace, "diff", "--no-index", "--", os.devnull, rel)
    return (p.stdout or "").strip()


def diff(
    workspace: str,
    paths: list[str] | None = None,
    baseline_index: str | None = None,
) -> str:
    env = _index_env(baseline_index)
    if baseline_index:
        args = ["diff"]
        if paths:
            args += ["--", *paths]
        p = _git(workspace, *args, env=env)
        chunks = [p.stdout.strip()]
        others = _git(workspace, "ls-files", "--others", "--exclude-standard", env=env)
        for rel in others.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            if paths and rel not in paths:
                continue
            extra = _untracked_diff(workspace, rel)
            if extra:
                chunks.append(extra)
        text = "\n".join(c for c in chunks if c).strip()
        return text[:20000] or "(no diff)"
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


def _parse_porcelain(stdout: str) -> list[str]:
    files: list[str] = []
    for line in stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def changed_files(workspace: str, baseline_index: str | None = None) -> list[str]:
    if not baseline_index:
        p = _git(workspace, "status", "--porcelain")
        return _parse_porcelain(p.stdout)
    env = _index_env(baseline_index)
    files: list[str] = []
    p = _git(workspace, "diff", "--name-only", env=env)
    files.extend(x.strip() for x in p.stdout.splitlines() if x.strip())
    others = _git(workspace, "ls-files", "--others", "--exclude-standard", env=env)
    files.extend(x.strip() for x in others.stdout.splitlines() if x.strip())
    return list(dict.fromkeys(files))


def diff_check(workspace: str) -> dict:
    if not (Path(workspace) / ".git").exists():
        return {"ok": True, "output": "not a git repo"}
    p = _git(workspace, "diff", "--check")
    return {"ok": p.returncode == 0, "output": (p.stdout + p.stderr)[-4000:]}
