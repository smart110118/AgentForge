"""Local Observer: captures session history, local file edits, and tool calls from IDE/CLI workspaces."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from local_agent.events.gateway import EventGateway
from local_agent.events.schema import EventClient, EventSource, ObserverType, StandardAgentEvent, StandardEventType


class LocalObserver:
    """Monitors local session files, logs, and tool execution traces to feed into EventGateway."""

    def __init__(
        self,
        gateway: EventGateway,
        client: EventClient | str = EventClient.CURSOR,
        session_id: str = "default_session",
    ) -> None:
        self.gateway = gateway
        self.client = client
        self.session_id = session_id

    def record_user_prompt(self, prompt: str, metadata: dict[str, Any] | None = None) -> StandardAgentEvent | None:
        """Capture a user prompt input event."""
        payload = {"prompt": prompt}
        if metadata:
            payload.update(metadata)

        return self.gateway.ingest(
            {
                "client": self.client,
                "observer": ObserverType.LOCAL,
                "session_id": self.session_id,
                "type": StandardEventType.USER_PROMPT,
                "payload": payload,
                "timestamp": time.time(),
            }
        )

    def record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | str,
        result: Any | None = None,
        exit_code: int = 0,
        error: str | None = None,
    ) -> StandardAgentEvent | None:
        """Capture tool invocation lifecycle event (e.g. bash, edit, read)."""
        is_failure = (exit_code != 0) or (error is not None)
        event_type = StandardEventType.TOOL_CALL_FAILED if is_failure else StandardEventType.TOOL_CALL_COMPLETE

        payload: dict[str, Any] = {
            "tool": tool_name,
            "arguments": arguments,
            "exit_code": exit_code,
        }
        if result is not None:
            payload["result_preview"] = str(result)[:500]
        if error:
            payload["error"] = error

        return self.gateway.ingest(
            {
                "client": self.client,
                "observer": ObserverType.LOCAL,
                "session_id": self.session_id,
                "type": event_type,
                "payload": payload,
                "timestamp": time.time(),
            }
        )

    def scan_session_log(self, log_path: str | Path) -> list[StandardAgentEvent]:
        """Parse structured JSONL session logs (e.g. from Claude Code or Codex) and ingest."""
        path = Path(log_path)
        if not path.exists():
            return []

        ingested: list[StandardAgentEvent] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        # Fill default source info
                        data.setdefault("client", self.client)
                        data.setdefault("observer", ObserverType.LOCAL)
                        data.setdefault("session_id", self.session_id)
                        evt = self.gateway.ingest(data)
                        if evt:
                            ingested.append(evt)
                except json.JSONDecodeError:
                    continue
        return ingested
