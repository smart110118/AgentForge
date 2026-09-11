from __future__ import annotations

from pathlib import Path

from local_agent.config import load_config
from local_agent.context.repo_map import repo_map
from local_agent.security.sandbox import allowed_by_globs
from local_agent.tasks.schema import Task
from local_agent.tools import git as git_tools
from local_agent.tools.filesystem import SKIP_DIRS, read_file


def _candidate_files(task: Task, limit: int) -> list[str]:
    ws = Path(task.workspace)
    globs = task.allow
    found: list[str] = []
    for p in ws.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file():
            continue
        rel = str(p.relative_to(ws))
        if allowed_by_globs(rel, globs):
            found.append(rel)
        if len(found) >= limit:
            break
    return found


def build(task: Task, extra: str = "") -> str:
    cfg = load_config().get("agent") or {}
    depth = int(cfg.get("tree_depth") or 2)
    file_limit = int(cfg.get("context_file_limit") or 12)
    char_limit = int(cfg.get("context_file_chars") or 8000)
    chunks = [
        f"# Task\n{task.objective}",
        "# Acceptance\n" + "\n".join(f"- {a}" for a in task.acceptance),
        "# Repo map\n" + repo_map(task.workspace, depth=depth),
    ]
    if task.feedback:
        chunks.append("# Reviewer feedback\n" + "\n".join(f"- {x}" for x in task.feedback))
    files = _candidate_files(task, file_limit)
    code = []
    for rel in files:
        try:
            text = read_file(task.workspace, rel, task.allow)
        except OSError:
            continue
        code.append(f"## {rel}\n{text[:char_limit]}")
    if code:
        chunks.append("# Relevant files\n" + "\n\n".join(code))
    try:
        chunks.append("# Git diff\n" + git_tools.diff(task.workspace))
    except OSError:
        pass
    if extra:
        chunks.append("# Errors / last test\n" + extra[-6000:])
    return "\n\n".join(chunks)
