from __future__ import annotations

from typing import Any

import httpx


class OpenAICompatibleClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        timeout: float = 180,
        http: httpx.Client | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.http = http or httpx.Client(timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        r = self.http.post(f"{self.endpoint}/chat/completions", json=body)
        r.raise_for_status()
        return r.json()
