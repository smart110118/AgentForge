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


def build(task: Task, extra: str = "", baseline_index: str = "") -> str:
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
    files: list[str] = []
    if baseline_index:
        for rel in git_tools.changed_files(task.workspace, baseline_index=baseline_index):
            if allowed_by_globs(rel, task.allow) and rel not in files:
                files.append(rel)
    for rel in _candidate_files(task, file_limit):
        if rel not in files:
            files.append(rel)
    files = files[:file_limit]
    code = []
    for rel in files:
        try:
            text = read_file(task.workspace, rel, task.allow)
        except OSError:
            continue
        code.append(f"## {rel}\n{text[:char_limit]}")
    if code:
        chunks.append("# Relevant files (current working tree)\n" + "\n\n".join(code))
    if baseline_index:
        names = git_tools.status(task.workspace, baseline_index=baseline_index)
        chunks.append(
            "# Session paths already on disk — do not re-apply these as patches\n" + names
        )
    if extra:
        chunks.append("# Errors / last test\n" + extra[-6000:])
    return "\n\n".join(chunks)
