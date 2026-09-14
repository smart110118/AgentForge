from __future__ import annotations

import threading
from typing import Any

from local_agent.agent.runtime import run_task
from local_agent.tasks.dag import dag_spec, run_dag
from local_agent.tasks.manager import MANAGER, TaskRecord
from local_agent.tasks.state import TaskStatus

_threads: dict[str, threading.Thread] = {}


def _public(rec: TaskRecord) -> dict[str, Any]:
    return {
        "task_id": rec.task.task_id,
        "status": rec.status.value,
        "iteration": rec.iteration,
        "summary": rec.summary,
        "files_changed": rec.files_changed,
        "tests": {
            "passed": rec.tests.get("passed", 0),
            "failed": rec.tests.get("failed", 0),
        }
        if rec.tests
        else {},
        "diff_summary": rec.diff_summary,
        "error": rec.error,
        "escalate": rec.escalate,
    }


def execute(payload: dict[str, Any], wait: bool = True) -> dict[str, Any]:
    if dag_spec(payload):
        return run_dag(payload)
    rec = MANAGER.create(payload)
    if wait:
        run_task(rec)
        return _public(rec)
    t = threading.Thread(target=run_task, args=(rec,), daemon=True)
    _threads[rec.task.task_id] = t
    t.start()
    return {"task_id": rec.task.task_id, "status": rec.status.value, "iteration": rec.iteration}


def status(task_id: str) -> dict[str, Any]:
    rec = MANAGER.get(task_id)
    if not rec:
        return {"error": "unknown task_id"}
    return {"task_id": rec.task.task_id, "status": rec.status.value, "iteration": rec.iteration}


def result(task_id: str) -> dict[str, Any]:
    rec = MANAGER.get(task_id)
    if not rec:
        return {"error": "unknown task_id"}
    return _public(rec)


def retry(task_id: str, feedback: list[str], wait: bool = True) -> dict[str, Any]:
    rec = MANAGER.get(task_id)
    if not rec:
        return {"error": "unknown task_id"}
    rec.task.feedback.extend(feedback)
    rec.status = TaskStatus.queued
    rec.error = ""
    rec.escalate = False
    rec.cancel_event.clear()
    if wait:
        run_task(rec)
        return _public(rec)
    t = threading.Thread(target=run_task, args=(rec,), daemon=True)
    _threads[task_id] = t
    t.start()
    return {"task_id": task_id, "status": rec.status.value, "iteration": rec.iteration}


def cancel(task_id: str) -> dict[str, Any]:
    rec = MANAGER.get(task_id)
    if not rec:
        return {"error": "unknown task_id"}
    rec.cancel_event.set()
    rec.status = TaskStatus.cancelled
    return {"task_id": task_id, "status": rec.status.value}
