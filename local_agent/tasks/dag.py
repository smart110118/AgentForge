from __future__ import annotations

from typing import Any

from local_agent.agent.runtime import run_task
from local_agent.tasks.manager import MANAGER
from local_agent.tasks.state import TaskStatus


def dag_spec(payload: dict[str, Any]) -> dict[str, Any] | None:
    spec = payload.get("specification") or {}
    dag = payload.get("dag") or spec.get("dag")
    if isinstance(dag, dict) and dag.get("tasks"):
        return dag
    return None


def toposort(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for t in tasks:
        tid = str(t.get("task_id") or "")
        if not tid:
            raise ValueError("dag node missing task_id")
        if tid in by_id:
            raise ValueError(f"duplicate task_id: {tid}")
        by_id[tid] = t
    incoming: dict[str, set[str]] = {}
    for t in tasks:
        tid = str(t["task_id"])
        deps = [str(x) for x in (t.get("depends_on") or [])]
        for d in deps:
            if d not in by_id:
                raise ValueError(f"unknown depends_on: {d}")
        incoming[tid] = set(deps)
    ready = [i for i, d in incoming.items() if not d]
    order: list[dict[str, Any]] = []
    seen: set[str] = set()
    while ready:
        n = ready.pop(0)
        if n in seen:
            continue
        seen.add(n)
        order.append(by_id[n])
        for i, deps in incoming.items():
            if n in deps:
                deps.remove(n)
                if not deps and i not in seen and i not in ready:
                    ready.append(i)
    if len(order) != len(tasks):
        raise ValueError("dag cycle")
    return order


def run_dag(payload: dict[str, Any]) -> dict[str, Any]:
    dag = dag_spec(payload) or {}
    # ponytail: parallel ignored beyond 1 until VRAM allows
    nodes = toposort(list(dag["tasks"]))
    workspace = str(payload["workspace"])
    results: list[dict[str, Any]] = []
    files: list[str] = []
    last_tests: dict[str, Any] = {}
    last_diff = ""
    overall = "success"
    parent_id = str(payload.get("task_id") or "dag")
    for node in nodes:
        child = {
            "task_id": str(node["task_id"]),
            "workspace": workspace,
            "objective": str(node.get("objective") or payload.get("objective") or ""),
            "files": node.get("files") or payload.get("files") or {},
            "acceptance": node.get("acceptance") or payload.get("acceptance") or [],
            "test": node.get("test") or payload.get("test") or {},
            "execution": node.get("execution") or payload.get("execution") or {},
        }
        rec = MANAGER.create(child)
        run_task(rec)
        results.append(
            {
                "task_id": rec.task.task_id,
                "status": rec.status.value,
                "error": rec.error,
                "files_changed": rec.files_changed,
            }
        )
        files.extend(rec.files_changed)
        if rec.tests:
            last_tests = rec.tests
        if rec.diff_summary:
            last_diff = rec.diff_summary
        if rec.status != TaskStatus.success:
            overall = rec.status.value
            break
    tests = {}
    if last_tests:
        tests = {"passed": last_tests.get("passed", 0), "failed": last_tests.get("failed", 0)}
    return {
        "task_id": parent_id,
        "status": overall,
        "iteration": len(results),
        "summary": f"dag {overall} ({len(results)} nodes)",
        "files_changed": list(dict.fromkeys(files)),
        "tests": tests,
        "diff_summary": last_diff,
        "error": "" if overall == "success" else (results[-1].get("error") if results else "dag failed"),
        "escalate": overall == "failed",
        "dag": results,
    }
