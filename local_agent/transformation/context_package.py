"""Context Package: standard immutable delivery package containing Snapshot, Diff, Graph, and Provenance."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from local_agent.events.store import EventStore
from local_agent.transformation.compressor import CompressorEngine
from local_agent.transformation.snapshot import RuntimeSnapshot, SnapshotEngine


@dataclass
class DependencyGraph:
    """Lightweight mapping of file/module imports and call relationships."""
    nodes: list[str] = field(default_factory=list)  # filenames / modules
    edges: list[dict[str, str]] = field(default_factory=list)  # [{"from": "a.py", "to": "b.py", "type": "imports"}]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceRecord:
    """Provenance and audit trail explaining the causal origin of the task handoff."""
    trace_id: str = ""
    initiating_client: str = ""
    key_decisions: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    test_exit_code: int = 0
    reason_for_package: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextPackage:
    """Standard v2.1 Context Package for downstream Target Agent consumption."""
    package_id: str = field(default_factory=lambda: f"pkg_{uuid.uuid4().hex[:12]}")
    created_at: float = field(default_factory=time.time)
    snapshot: RuntimeSnapshot | None = None
    diff: str = ""
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    provenance: ProvenanceRecord = field(default_factory=ProvenanceRecord)
    code_skeletons: dict[str, str] = field(default_factory=dict)  # filepath -> folded skeleton

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "snapshot": self.snapshot.to_dict() if self.snapshot else {},
            "diff": self.diff,
            "graph": self.graph.to_dict(),
            "provenance": self.provenance.to_dict(),
            "code_skeletons": self.code_skeletons,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Render a clean Markdown prompt suitable for downstream Target Agent context."""
        snap = self.snapshot
        head = snap.git_head if snap else "unknown"
        modified = ", ".join(snap.modified_files) if (snap and snap.modified_files) else "None"

        skeletons_md = ""
        if self.code_skeletons:
            skeletons_md = "\n### Code Skeletons (AST Folded)\n"
            for fpath, skel in self.code_skeletons.items():
                skeletons_md += f"#### `{fpath}`\n```python\n{skel}\n```\n"

        diff_md = f"```diff\n{self.diff}\n```" if self.diff else "No uncommitted git diff."

        return f"""# Context Package: `{self.package_id}`

## 1. Snapshot & Environment
- **Git HEAD**: `{head}`
- **Modified Files**: {modified}
- **Python Version**: {snap.python_version if snap else "unknown"}
- **OS**: {snap.os_info if snap else "unknown"}

## 2. Provenance & Decisions
- **Trace ID**: `{self.provenance.trace_id}`
- **Origin Client**: `{self.provenance.initiating_client}`
- **Reason**: {self.provenance.reason_for_package}
- **Key Decisions**:
{chr(10).join(f"  - {d}" for d in self.provenance.key_decisions) if self.provenance.key_decisions else "  - None"}
- **Recent Errors**:
{chr(10).join(f"  - `{e}`" for e in self.provenance.recent_errors) if self.provenance.recent_errors else "  - None"}

## 3. Active Changes (Git Diff)
{diff_md}

{skeletons_md}
"""


class ContextPackageBuilder:
    """Constructs and serializes ContextPackage from workspace, event store, and engines."""

    def __init__(self, workspace: str | Path, store: EventStore | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.store = store
        self.snapshot_engine = SnapshotEngine(self.workspace)
        self.compressor = CompressorEngine()

    def build(
        self,
        session_id: str = "",
        reason: str = "Handoff to target agent",
        skeleton_files: list[str] | None = None,
    ) -> ContextPackage:
        # 1. Snapshot
        snapshot = self.snapshot_engine.capture()

        # 2. Diff
        diff_text = snapshot.git_diff

        # 3. Provenance extraction from EventStore
        provenance = ProvenanceRecord(
            trace_id=f"trace_{session_id}" if session_id else "default_trace",
            initiating_client="cursor",
            reason_for_package=reason,
        )

        if self.store and session_id:
            events = self.store.query(session_id=session_id, limit=30, descending=False)
            for e in events:
                payload = e.payload or {}
                if e.source and hasattr(e.source, "client") and e.source.client:
                    provenance.initiating_client = str(getattr(e.source.client, "value", e.source.client))
                if "prompt" in payload:
                    provenance.key_decisions.append(f"Prompt: {payload['prompt'][:80]}")
                if "error" in payload:
                    provenance.recent_errors.append(str(payload["error"])[:120])
                if "exit_code" in payload:
                    provenance.test_exit_code = int(payload["exit_code"])

        # 4. AST Skeletons
        skeletons: dict[str, str] = {}
        files_to_skeleton = skeleton_files or snapshot.modified_files
        for rel_path in files_to_skeleton:
            full_path = self.workspace / rel_path
            if full_path.exists() and full_path.suffix == ".py":
                try:
                    content = full_path.read_text(encoding="utf-8")
                    skeletons[rel_path] = self.compressor.extract_python_skeleton(content)
                except Exception:
                    pass

        # 5. Dependency Graph (simple module imports)
        graph = DependencyGraph(nodes=list(skeletons.keys()))
        for src_file in skeletons:
            graph.edges.append({"from": src_file, "to": "workspace", "type": "member_of"})

        return ContextPackage(
            snapshot=snapshot,
            diff=diff_text,
            graph=graph,
            provenance=provenance,
            code_skeletons=skeletons,
        )
