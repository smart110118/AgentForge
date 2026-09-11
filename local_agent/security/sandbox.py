from __future__ import annotations

from pathlib import Path, PurePosixPath
import fnmatch


class SandboxError(PermissionError):
    pass


def resolve_in_workspace(workspace: str, path: str) -> Path:
    ws = Path(workspace).resolve()
    raw = Path(path)
    target = raw.resolve() if raw.is_absolute() else (ws / raw).resolve()
    try:
        target.relative_to(ws)
    except ValueError as e:
        raise SandboxError(f"path outside workspace: {path}") from e
    return target


def relpath(workspace: str, path: Path) -> str:
    ws = Path(workspace).resolve()
    return str(path.resolve().relative_to(ws))


def allowed_by_globs(rel: str, globs: list[str]) -> bool:
    if not globs:
        return True
    posix = str(PurePosixPath(rel))
    path = PurePosixPath(rel)
    for g in globs:
        g = g.replace("\\", "/")
        if g in {"**", "**/*", "*"}:
            return True
        if path.match(g) or fnmatch.fnmatch(posix, g):
            return True
        if g.endswith("/**"):
            prefix = g[:-3].rstrip("/")
            if posix == prefix or posix.startswith(prefix + "/"):
                return True
    return False
