import pytest
from pathlib import Path

from local_agent.events import EventClient, EventSource, EventStore, StandardAgentEvent, StandardEventType
from local_agent.transformation import (
    CompressorEngine,
    ContextPackage,
    ContextPackageBuilder,
    SnapshotEngine,
)


def test_compressor_output_truncation():
    # Generate 50 lines of output
    long_output = "\n".join([f"Log line {i}: normal operation status" for i in range(50)])
    truncated = CompressorEngine.truncate_output(long_output, head_lines=5, tail_lines=5)

    assert "Log line 0" in truncated
    assert "Log line 4" in truncated
    assert "omitted" in truncated
    assert "Log line 45" in truncated
    assert "Log line 49" in truncated
    assert len(truncated) < len(long_output)


def test_ast_python_skeleton_folding():
    sample_code = """
import os
import sys

class Worker:
    \"\"\"Worker class docstring.\"\"\"
    def __init__(self, name: str):
        self.name = name
        self.count = 0
        for i in range(10):
            self.count += i

    def execute_task(self, task_id: int) -> bool:
        \"\"\"Runs the task.\"\"\"
        if task_id < 0:
            raise ValueError("Invalid id")
        print("Running task", task_id)
        return True

def standalone_func(x: int, y: int) -> int:
    return x + y
"""
    skeleton = CompressorEngine.extract_python_skeleton(sample_code)

    # Class and function declarations should be retained
    assert "class Worker:" in skeleton
    assert "def __init__(self, name: str):" in skeleton
    assert "def execute_task(self, task_id: int) -> bool:" in skeleton
    assert "def standalone_func(x: int, y: int) -> int:" in skeleton

    # Docstring should be preserved
    assert "Worker class docstring" in skeleton
    assert "Runs the task." in skeleton

    # Implementation details should be folded to Ellipsis
    assert "raise ValueError" not in skeleton
    assert "print(\"Running task\"" not in skeleton
    assert "..." in skeleton


def test_snapshot_engine(tmp_path: Path):
    engine = SnapshotEngine(tmp_path)
    snapshot = engine.capture()

    assert snapshot.workspace_path == str(tmp_path.resolve())
    assert snapshot.python_version != ""
    assert snapshot.os_info != ""


def test_context_package_build_and_render(tmp_path: Path):
    # Create a dummy python file in workspace
    dummy_file = tmp_path / "service.py"
    dummy_file.write_text(
        """
def compute(data: list[int]) -> int:
    \"\"\"Compute sum.\"\"\"
    total = 0
    for v in data:
        total += v
    return total
""",
        encoding="utf-8",
    )

    store = EventStore(":memory:")
    sess_id = "test_pkg_sess"
    store.append(
        StandardAgentEvent(
            source=EventSource(client=EventClient.CURSOR, session_id=sess_id),
            type=StandardEventType.USER_PROMPT,
            payload={"prompt": "Refactor compute to use built-in sum()"},
        )
    )

    builder = ContextPackageBuilder(workspace=tmp_path, store=store)
    pkg = builder.build(
        session_id=sess_id,
        reason="Handoff to Specialist Agent",
        skeleton_files=["service.py"],
    )

    assert pkg.package_id.startswith("pkg_")
    assert "service.py" in pkg.code_skeletons
    assert "def compute(data: list[int]) -> int:" in pkg.code_skeletons["service.py"]
    assert "total = 0" not in pkg.code_skeletons["service.py"]

    # Test Markdown serialization
    md = pkg.to_markdown()
    assert "# Context Package:" in md
    assert "Refactor compute" in md
    assert "Code Skeletons" in md

    # Test JSON serialization
    json_str = pkg.to_json()
    assert "package_id" in json_str
