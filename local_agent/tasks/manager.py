from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from local_agent.tasks.schema import Task, parse_task
from local_agent.tasks.state import TaskStatus


@dataclass
class TaskRecord:
    task: Task
    status: TaskStatus = TaskStatus.queued
    iteration: int = 0
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    diff_summary: str = ""
    tests: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    escalate: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: float = field(default_factory=time.time)
    baseline_index: str = ""


class TaskManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, TaskRecord] = {}

    def create(self, data: dict[str, Any]) -> TaskRecord:
        payload = dict(data)
        payload.setdefault("task_id", f"task-{uuid.uuid4().hex[:10]}")
        task = parse_task(payload)
        rec = TaskRecord(task=task)
        with self._lock:
            self._items[task.task_id] = rec
        return rec

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._items.get(task_id)

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        rec = self.get(task_id)
        if rec:
            rec.status = status


MANAGER = TaskManager()
