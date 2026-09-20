from __future__ import annotations

import json
import re
from typing import Any

from local_agent.config import load_config
from local_agent.context.manager import build as build_context
from local_agent.models.qwen import qwen_client
from local_agent.security.policy import PolicyError
from local_agent.security.sandbox import SandboxError
from local_agent.security.sandbox import allowed_by_globs
from local_agent.tasks.manager import TaskRecord
from local_agent.tasks.state import TaskStatus
from local_agent.tools import filesystem, git as git_tools
from local_agent.tools.shell import execute as shell_execute
from local_agent.tools.tests import run_gate
from typesafe.compact import compact_history

SYSTEM = """You are a local coding executor. Implement the task using tools.
Do not modify files outside the allowed paths.
Edit from current working-tree file contents (read_file). Never re-apply a git diff or a patch that is already in the file.
When done, call finish with a short summary.
If tests fail, fix the code and try again."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files under a relative directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search workspace for a pattern",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Replace the first occurrence of old with new in a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["path", "old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run an allowlisted shell command in the workspace",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "git status --porcelain",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Session diff already on disk; do not re-apply. Not vs HEAD.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "git log --oneline",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the task test command",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Mark implementation complete",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]


def _args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def parse_actions(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    blob = fence.group(1) if fence else text
    start, end = blob.find("{"), blob.rfind("}")
    if start == -1 or end == -1:
        start, end = blob.find("["), blob.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        obj = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return []
    items = obj if isinstance(obj, list) else [obj]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("tool") or item.get("action")
        if not name:
            continue
        args = item.get("arguments") or item.get("args") or item
        if not isinstance(args, dict):
            args = {}
        out.append({"name": name, "arguments": {k: v for k, v in args.items() if k not in ("name", "tool", "action", "arguments", "args")}})
        if name in args:
            out[-1]["arguments"] = {k: v for k, v in args.items() if k != "name"}
    return out


def execute_tool(rec: TaskRecord, name: str, args: dict[str, Any]) -> str:
    task = rec.task
    ws, globs = task.workspace, task.allow
    try:
        if name == "list_files":
            return "\n".join(filesystem.list_files(ws, args.get("path") or ".", globs)) or "(empty)"
        if name == "read_file":
            return filesystem.read_file(ws, args["path"], globs)
        if name == "search":
            return filesystem.search(ws, args["pattern"], globs)
        if name == "write_file":
            rel, changed = filesystem.write_file(ws, args["path"], args.get("content") or "", globs)
            if changed and rel not in rec.files_changed:
                rec.files_changed.append(rel)
            return f"wrote {rel}" if changed else f"unchanged {rel} — already on disk, do not replay"
        if name == "patch_file":
            rel, changed = filesystem.patch_file(ws, args["path"], args["old"], args["new"], globs)
            if changed and rel not in rec.files_changed:
                rec.files_changed.append(rel)
            return f"patched {rel}" if changed else f"already applied {rel} — do not replay this diff"
        if name == "shell":
            return json.dumps(shell_execute(args["command"], ws))
        if name == "git_status":
            return git_tools.status(ws, baseline_index=rec.baseline_index or None)
        if name == "git_diff":
            body = git_tools.diff(ws, baseline_index=rec.baseline_index or None)
            return "Already on disk this session. Do not re-apply these hunks.\n" + body
        if name == "git_log":
            return git_tools.log(ws)
        if name == "run_tests":
            if not task.test_command:
                return "no test command"
            return json.dumps(run_gate(ws, task.test_command))
        if name == "finish":
            rec.summary = str(args.get("summary") or rec.summary)
            return "ok"
        return f"unknown tool: {name}"
    except (SandboxError, PolicyError, ValueError, OSError, KeyError) as e:
        return f"error: {e}"


def _snapshot(rec: TaskRecord) -> None:
    written = list(rec.files_changed)
    baseline = rec.baseline_index or None
    git_files = git_tools.changed_files(rec.task.workspace, baseline_index=baseline)
    globs = rec.task.allow
    if globs:
        git_ok = [f for f in git_files if allowed_by_globs(f, globs)]
        rec.files_changed = list(dict.fromkeys(written + git_ok))
    else:
        rec.files_changed = written
    rec.diff_summary = git_tools.diff(
        rec.task.workspace, rec.files_changed or None, baseline_index=baseline
    )[:4000]


def _maybe_gate(rec: TaskRecord) -> dict | None:
    if not rec.task.test_command:
        return None
    gate = run_gate(rec.task.workspace, rec.task.test_command)
    rec.tests = {
        "passed": (gate.get("tests") or {}).get("passed", 0),
        "failed": (gate.get("tests") or {}).get("failed", 0),
        "exit_code": (gate.get("tests") or {}).get("exit_code"),
        "output": (gate.get("tests") or {}).get("output", ""),
        "git_diff_check": gate.get("git_diff_check"),
    }
    return gate


STALL_HINT = (
    "Working tree did not change. Diff hunks are already on disk — do not re-apply them. "
    "read_file current sources and implement only remaining work, then finish."
)


def _bump_stall(rec: TaskRecord, last_diff: str | None, stalls: int) -> tuple[str, int]:
    cur = rec.diff_summary
    if last_diff is not None and cur == last_diff:
        return cur, stalls + 1
    return cur, 0


def _stop_stall(rec: TaskRecord) -> TaskRecord:
    rec.error = "stalled: working tree unchanged (diff already applied)"
    rec.escalate = True
    if not rec.task.test_command and rec.files_changed:
        rec.status = TaskStatus.success
        rec.summary = rec.summary or "stalled after writes"
        rec.error = ""
        rec.escalate = False
        return rec
    rec.status = TaskStatus.failed
    return rec


def run_task(rec: TaskRecord, client: Any | None = None) -> TaskRecord:
    rec.status = TaskStatus.running
    rec.cancel_event.clear()
    rec.files_changed = []
    rec.diff_summary = ""
    rec.error = ""
    rec.escalate = False
    cfg = load_config()
    client = client or qwen_client(cfg)
    temp = float((cfg.get("agent") or {}).get("temperature") or 0.2)
    max_iter = rec.task.max_iterations
    extra = ""
    history: list[dict[str, Any]] = []
    want_finish = False
    last_diff: str | None = None
    stalls = 0
    rec.baseline_index = git_tools.capture_baseline(rec.task.workspace) or ""

    try:
        for i in range(max_iter):
            if rec.cancel_event.is_set():
                rec.status = TaskStatus.cancelled
                rec.error = "cancelled"
                return rec
            rec.iteration = i + 1
            history = compact_history(history, rec.task.objective)
            user = build_context(rec.task, extra=extra, baseline_index=rec.baseline_index)
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}, *history]
            data = client.chat(messages, tools=TOOLS, temperature=temp)
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            actions: list[tuple[str, dict[str, Any], str | None]] = []
            if tool_calls:
                history.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function") or {}
                    actions.append((fn.get("name") or "", _args(fn.get("arguments")), tc.get("id")))
            else:
                parsed = parse_actions(content)
                if parsed:
                    history.append({"role": "assistant", "content": content})
                    for a in parsed:
                        actions.append((a["name"], a.get("arguments") or {}, None))
                elif content:
                    history.append({"role": "assistant", "content": content})

            if not actions:
                gate = _maybe_gate(rec)
                _snapshot(rec)
                last_diff, stalls = _bump_stall(rec, last_diff, stalls)
                if stalls >= 2:
                    return _stop_stall(rec)
                if rec.task.test_command:
                    if gate and gate["ok"] and rec.files_changed:
                        rec.status = TaskStatus.success
                        rec.summary = rec.summary or content[:500]
                        return rec
                    extra = (rec.tests or {}).get("output") or (
                        "Tests pass but no files changed. Use write_file."
                        if gate and gate["ok"]
                        else "tests failed"
                    )
                    extra = extra + "\n" + STALL_HINT if stalls else extra
                    continue
                if rec.files_changed:
                    rec.status = TaskStatus.success
                    rec.summary = rec.summary or content[:500] or "done"
                    return rec
                extra = "No tool calls. Use write_file or finish."
                continue

            finished = False
            for name, args, call_id in actions:
                result = execute_tool(rec, name, args)
                if call_id:
                    history.append({"role": "tool", "tool_call_id": call_id, "content": result[:8000]})
                else:
                    history.append({"role": "user", "content": f"tool {name} -> {result[:8000]}"})
                if name == "finish":
                    finished = True
                    want_finish = True

            gate = _maybe_gate(rec)
            _snapshot(rec)
            last_diff, stalls = _bump_stall(rec, last_diff, stalls)
            if stalls >= 2:
                extra = STALL_HINT
                return _stop_stall(rec)
            if rec.task.test_command:
                if gate and gate["ok"]:
                    rec.status = TaskStatus.success
                    rec.summary = rec.summary or "tests passed"
                    return rec
                extra = ((rec.tests or {}).get("output") or json.dumps(gate)) + "\n" + STALL_HINT
                continue
            if finished:
                rec.status = TaskStatus.success
                rec.summary = rec.summary or "done"
                return rec
            extra = STALL_HINT if stalls else extra

        _snapshot(rec)
        if not rec.task.test_command and rec.files_changed:
            rec.status = TaskStatus.success
            rec.summary = rec.summary or "wrote files"
            return rec
        rec.escalate = True
        rec.status = TaskStatus.failed
        rec.error = rec.error or "max_iterations exceeded"
        return rec
    except Exception as e:
        rec.status = TaskStatus.failed
        rec.error = str(e)
        return rec
    finally:
        git_tools.drop_baseline(rec.baseline_index or None)
        rec.baseline_index = ""
