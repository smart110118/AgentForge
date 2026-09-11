from __future__ import annotations

from pathlib import Path

from local_agent.tools.filesystem import SKIP_DIRS

MARKERS = ("README.md", "README", "pyproject.toml", "package.json", "go.mod", "Cargo.toml")


def repo_map(workspace: str, depth: int = 2) -> str:
    ws = Path(workspace)
    parts: list[str] = []
    for name in MARKERS:
        p = ws / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")[:1500]
            parts.append(f"## {name}\n{text}")
    tree: list[str] = []

    def walk(d: Path, dpth: int, prefix: str) -> None:
        if dpth > depth:
            return
        try:
            kids = sorted(d.iterdir(), key=lambda x: x.name)
        except OSError:
            return
        for child in kids:
            if child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            tree.append(f"{prefix}{child.name}{'/' if child.is_dir() else ''}")
            if child.is_dir():
                walk(child, dpth + 1, prefix + "  ")

    walk(ws, 1, "")
    parts.append("## tree\n" + "\n".join(tree[:200]))
    return "\n\n".join(parts)
