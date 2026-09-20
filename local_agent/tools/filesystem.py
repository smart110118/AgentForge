from __future__ import annotations

import subprocess
from pathlib import Path

from local_agent.security.sandbox import (
    SandboxError,
    allowed_by_globs,
    relpath,
    resolve_in_workspace,
)

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


def _check_allow(workspace: str, path: Path, globs: list[str]) -> str:
    rel = relpath(workspace, path)
    if not allowed_by_globs(rel, globs):
        raise SandboxError(f"path not in files.allow: {rel}")
    return rel


def list_files(workspace: str, rel: str = ".", globs: list[str] | None = None) -> list[str]:
    globs = globs or []
    root = resolve_in_workspace(workspace, rel)
    if root.is_file():
        _check_allow(workspace, root, globs)
        return [relpath(workspace, root)]
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        r = relpath(workspace, p)
        if allowed_by_globs(r, globs):
            out.append(r)
        if len(out) >= 400:
            break
    return out


def read_file(workspace: str, path: str, globs: list[str] | None = None) -> str:
    target = resolve_in_workspace(workspace, path)
    _check_allow(workspace, target, globs or [])
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(workspace: str, path: str, content: str, globs: list[str] | None = None) -> tuple[str, bool]:
    target = resolve_in_workspace(workspace, path)
    _check_allow(workspace, target, globs or [])
    rel = relpath(workspace, target)
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return rel, False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return rel, True


def patch_file(workspace: str, path: str, old: str, new: str, globs: list[str] | None = None) -> tuple[str, bool]:
    target = resolve_in_workspace(workspace, path)
    _check_allow(workspace, target, globs or [])
    rel = relpath(workspace, target)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        if new and new in text:
            return rel, False
        raise ValueError(
            f"old text not found in {path}. File already differs; read_file and edit current contents. Do not replay a git diff."
        )
    if old == new:
        return rel, False
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return rel, True


def search(workspace: str, pattern: str, globs: list[str] | None = None) -> str:
    ws = Path(workspace).resolve()
    rg = subprocess.run(
        ["rg", "-n", "--hidden", "--glob", "!.git", pattern, str(ws)],
        capture_output=True,
        text=True,
    )
    if rg.returncode in (0, 1) and (rg.stdout or not rg.stderr):
        lines = []
        for line in rg.stdout.splitlines()[:80]:
            try:
                path_part = line.split(":", 1)[0]
                rel = relpath(workspace, Path(path_part))
            except Exception:
                continue
            if allowed_by_globs(rel, globs or []):
                lines.append(line)
        return "\n".join(lines) or "(no matches)"
    hits: list[str] = []
    for p in ws.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file():
            continue
        try:
            rel = relpath(workspace, p)
        except ValueError:
            continue
        if not allowed_by_globs(rel, globs or []):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern in line:
                hits.append(f"{rel}:{i}:{line[:200]}")
                if len(hits) >= 80:
                    return "\n".join(hits)
    return "\n".join(hits) or "(no matches)"
