from __future__ import annotations

import json
from typing import Any

import httpx


def responses_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tools or []:
        fn = t.get("function") if t.get("type") == "function" else None
        if isinstance(fn, dict):
            out.append(
                {
                    "type": "function",
                    "name": fn.get("name"),
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        else:
            out.append(t)
    return out


def messages_to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": m.get("tool_call_id"),
                    "output": m.get("content") or "",
                }
            )
            continue
        if role == "assistant" and m.get("tool_calls"):
            if m.get("content"):
                items.append({"role": "assistant", "content": m["content"]})
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                if not isinstance(args, str):
                    args = json.dumps(args or {})
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.get("id"),
                        "name": fn.get("name"),
                        "arguments": args,
                    }
                )
            continue
        if role in ("system", "user", "assistant"):
            items.append({"role": role, "content": m.get("content") or ""})
    return items


def responses_to_chat(data: dict[str, Any]) -> dict[str, Any]:
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for item in data.get("output") or []:
        kind = item.get("type")
        if kind == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    texts.append(c["text"])
        elif kind == "function_call":
            tool_calls.append(
                {
                    "id": item.get("call_id") or item.get("id"),
                    "type": "function",
                    "function": {
                        "name": item.get("name"),
                        "arguments": item.get("arguments") or "{}",
                    },
                }
            )
    msg: dict[str, Any] = {"role": "assistant", "content": "\n".join(texts)}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}], "id": data.get("id"), "model": data.get("model")}


class OpenAICompatibleClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        timeout: float = 180,
        http: httpx.Client | None = None,
        api: str = "responses",
        api_key: str = "",
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api = api
        self.api_key = api_key or ""
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        self.http = http or httpx.Client(timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if self.api == "chat":
            body: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            r = self.http.post(
                f"{self.endpoint}/chat/completions", json=body, headers=self.headers or None
            )
            r.raise_for_status()
            return r.json()
        body = {
            "model": self.model,
            "input": messages_to_responses_input(messages),
            "temperature": temperature,
        }
        if tools:
            body["tools"] = responses_tools(tools)
        r = self.http.post(f"{self.endpoint}/responses", json=body, headers=self.headers or None)
        r.raise_for_status()
        return responses_to_chat(r.json())
