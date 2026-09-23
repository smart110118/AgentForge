"""Feedback Loop: captures target agent execution telemetry and writes back into EventStore."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from local_agent.events.schema import EventClient, EventSource, ObserverType, StandardAgentEvent, StandardEventType
from local_agent.events.store import EventStore


@dataclass
class TargetExecutionResult:
    handoff_id: str
    target_agent_id: str
    status: str  # "success", "failed", "completed"
    exit_code: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    files_changed: list[str] = field(default_factory=list)
    summary: str = ""
    error: str | None = None
    correlation_id: str = ""
    execution_duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeedbackLoop:
    """Closes the loop by receiving execution outcomes from Target Agents and writing them back into the EventStore."""

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def ingest_feedback(self, result: TargetExecutionResult) -> StandardAgentEvent:
        """Record the target agent's execution telemetry and results back into EventStore."""
        is_success = (result.exit_code == 0) and (result.tests_failed == 0) and (result.error is None)
        event_type = StandardEventType.TOOL_CALL_COMPLETE if is_success else StandardEventType.TOOL_CALL_FAILED

        payload: dict[str, Any] = {
            "handoff_id": result.handoff_id,
            "target_agent_id": result.target_agent_id,
            "status": result.status,
            "exit_code": result.exit_code,
            "tests": {
                "passed": result.tests_passed,
                "failed": result.tests_failed,
            },
            "files_changed": result.files_changed,
            "summary": result.summary,
            "duration_sec": result.execution_duration_sec,
        }
        if result.error:
            payload["error"] = result.error

        feedback_event = StandardAgentEvent(
            timestamp=time.time(),
            source=EventSource(
                client=EventClient.LOCAL_AGENT,
                observer=ObserverType.RUNTIME,
                session_id=result.handoff_id,
            ),
            type=event_type,
            payload=payload,
            correlation_id=result.correlation_id or f"corr_{result.handoff_id}",
            confidence=0.99,  # Target agent execution verification is high ground truth
        )

        self.store.append(feedback_event)
        return feedback_event
