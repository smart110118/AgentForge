"""Network Observer: intercepts LLM API traffic to record request telemetry and token usage."""

from __future__ import annotations

import time
from typing import Any

from local_agent.events.gateway import EventGateway
from local_agent.events.schema import EventClient, ObserverType, StandardAgentEvent, StandardEventType


class NetworkObserver:
    """Monitors outbound LLM API requests and incoming streaming/batch responses.
    Extracts usage metrics: prompt_tokens, completion_tokens, latency, provider, and model name.
    """

    def __init__(
        self,
        gateway: EventGateway,
        client: EventClient | str = EventClient.CURSOR,
        session_id: str = "default_session",
    ) -> None:
        self.gateway = gateway
        self.client = client
        self.session_id = session_id

    def record_request(
        self,
        model: str,
        messages_count: int,
        endpoint: str = "/chat/completions",
        correlation_id: str = "",
    ) -> StandardAgentEvent | None:
        """Record an outbound API request event."""
        return self.gateway.ingest(
            {
                "client": self.client,
                "observer": ObserverType.NETWORK,
                "session_id": self.session_id,
                "type": StandardEventType.API_REQUEST,
                "payload": {
                    "model": model,
                    "endpoint": endpoint,
                    "messages_count": messages_count,
                    "start_time": time.time(),
                },
                "correlation_id": correlation_id,
            }
        )

    def record_response(
        self,
        model: str,
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
        status_code: int = 200,
        correlation_id: str = "",
    ) -> StandardAgentEvent | None:
        """Record an incoming API response and token usage metrics."""
        usage_data = usage or {}
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        payload = {
            "model": model,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }

        # Also emit a dedicated usage metric event
        event = self.gateway.ingest(
            {
                "client": self.client,
                "observer": ObserverType.NETWORK,
                "session_id": self.session_id,
                "type": StandardEventType.USAGE_METRIC,
                "payload": payload,
                "correlation_id": correlation_id,
            }
        )
        return event

    def parse_openai_response(
        self,
        response_json: dict[str, Any],
        latency_ms: float = 0.0,
        correlation_id: str = "",
    ) -> StandardAgentEvent | None:
        """Helper to parse standard OpenAI-compatible API response dictionaries."""
        model = response_json.get("model", "unknown")
        usage = response_json.get("usage", {})
        return self.record_response(
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            status_code=200,
            correlation_id=correlation_id,
        )
