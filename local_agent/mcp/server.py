from __future__ import annotations

import json
import sys
from typing import Any

from local_agent.mcp import tools as api

TOOL_LIST = [
    {
        "name": "local_agent_execute",
        "description": "Submit a local coding task to Qwen. Set wait=true to block until done.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "workspace": {"type": "string"},
                "objective": {"type": "string"},
                "files": {"type": "object"},
                "acceptance": {"type": "array", "items": {"type": "string"}},
                "test_command": {"type": "string"},
                "test": {"type": "object"},
                "execution": {"type": "object"},
                "specification": {"type": "object"},
                "wait": {"type": "boolean", "default": True},
            },
            "required": ["workspace", "objective"],
        },
    },
    {
        "name": "local_agent_status",
        "description": "Get task status",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "local_agent_result",
        "description": "Get compact task result",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "local_agent_retry",
        "description": "Retry a task with reviewer feedback",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "feedback": {"type": "array", "items": {"type": "string"}},
                "wait": {"type": "boolean", "default": True},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "local_agent_cancel",
        "description": "Cancel a running task",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
]


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "local_agent_execute":
        wait = arguments.pop("wait", True)
        if arguments.get("test_command") and "test" not in arguments:
            arguments["test"] = {"command": arguments.pop("test_command")}
        else:
            arguments.pop("test_command", None)
        return api.execute(arguments, wait=bool(wait))
    if name == "local_agent_status":
        return api.status(arguments["task_id"])
    if name == "local_agent_result":
        return api.result(arguments["task_id"])
    if name == "local_agent_retry":
        return api.retry(arguments["task_id"], list(arguments.get("feedback") or []), wait=bool(arguments.get("wait", True)))
    if name == "local_agent_cancel":
        return api.cancel(arguments["task_id"])
    return {"error": f"unknown tool {name}"}


def _read() -> dict[str, Any] | None:
    buf = sys.stdin.buffer
    header = b""
    while True:
        line = buf.readline()
        if not line:
            return None
        if line in (b"\n", b"\r\n"):
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
            while True:
                h = buf.readline()
                if not h or h in (b"\n", b"\r\n"):
                    break
            body = buf.read(length)
            return json.loads(body.decode())
        header += line
        stripped = line.strip()
        if stripped:
            return json.loads(stripped.decode())
    return None


def _write(msg: dict[str, Any]) -> None:
    # MCP stdio is newline-delimited JSON (not LSP Content-Length).
    sys.stdout.buffer.write(json.dumps(msg, ensure_ascii=False).encode() + b"\n")
    sys.stdout.buffer.flush()


def _handle(req: dict[str, Any]) -> dict[str, Any] | None:
    mid = req.get("id")
    method = req.get("method")
    if method is None:
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": req.get("params", {}).get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "local-agent", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOL_LIST}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = _call(name, args)
            text = json.dumps(result, ensure_ascii=False)
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                    "isError": True,
                },
            }
    if method in ("resources/list", "resources/templates/list"):
        return {"jsonrpc": "2.0", "id": mid, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"prompts": []}}
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    while True:
        req = _read()
        if req is None:
            break
        resp = _handle(req)
        if resp is not None:
            _write(resp)


if __name__ == "__main__":
    main()
