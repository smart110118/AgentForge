from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _req(data: dict[str, Any], key: str) -> Any:
    if key not in data or data[key] in (None, ""):
        raise ValueError(f"missing field: {key}")
    return data[key]


@dataclass
class Task:
    task_id: str
    workspace: str
    objective: str
    specification: dict[str, Any] = field(default_factory=dict)
    files: dict[str, list[str]] = field(default_factory=dict)
    acceptance: list[str] = field(default_factory=list)
    test: dict[str, str] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    feedback: list[str] = field(default_factory=list)

    @property
    def allow(self) -> list[str]:
        return list(self.files.get("allow") or [])

    @property
    def test_command(self) -> str | None:
        cmd = (self.test or {}).get("command")
        return cmd or None

    @property
    def max_iterations(self) -> int:
        return int((self.execution or {}).get("max_iterations") or 8)

    @property
    def model(self) -> str:
        return str((self.execution or {}).get("model") or "qwen-coder")


def parse_task(data: dict[str, Any]) -> Task:
    if not isinstance(data, dict):
        raise ValueError("task must be an object")
    files = data.get("files") or {}
    if files and not isinstance(files, dict):
        raise ValueError("files must be an object")
    if "allow" in files and not isinstance(files["allow"], list):
        raise ValueError("files.allow must be a list")
    acceptance = data.get("acceptance") or []
    if not isinstance(acceptance, list):
        raise ValueError("acceptance must be a list")
    test = data.get("test") or {}
    if test and not isinstance(test, dict):
        raise ValueError("test must be an object")
    execution = data.get("execution") or {}
    if execution and not isinstance(execution, dict):
        raise ValueError("execution must be an object")
    spec = data.get("specification") or {}
    if spec and not isinstance(spec, dict):
        raise ValueError("specification must be an object")
    return Task(
        task_id=str(_req(data, "task_id")),
        workspace=str(_req(data, "workspace")),
        objective=str(_req(data, "objective")),
        specification=spec,
        files=files,
        acceptance=[str(x) for x in acceptance],
        test=test,
        execution=execution,
        feedback=[str(x) for x in (data.get("feedback") or [])],
    )
