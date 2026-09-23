"""Task Engine: infers execution phases and detects loops/stalls in tool calls."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from local_agent.events.schema import StandardAgentEvent, StandardEventType
from local_agent.events.store import EventStore


class TaskPhase(str, Enum):
    PLANNING = "planning"       # Initial exploration, repo inspection, reading docs
    CODING = "coding"           # Modifying or writing code files
    TESTING = "testing"         # Running tests or test suites
    FIXING = "fixing"           # Handling errors, assertions, or syntax fixes
    IDLE = "idle"


@dataclass
class StallDetectionResult:
    is_stalled: bool = False
    is_looping: bool = False
    repeated_command: str = ""
    repeat_count: int = 0
    consecutive_failures: int = 0
    warning: str = ""


class TaskEngine:
    """Tracks task state transitions and identifies tool invocation loops or debugging stalls."""

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def infer_phase(self, session_id: str) -> TaskPhase:
        """Infer the current task phase based on the latest sequence of SAE events."""
        events = self.store.query(session_id=session_id, limit=20, descending=True)
        if not events:
            return TaskPhase.IDLE

        for e in events:
            etype = e.type if isinstance(e.type, str) else e.type.value
            payload = e.payload or {}

            # Check failures
            if etype == StandardEventType.TOOL_CALL_FAILED.value or payload.get("exit_code", 0) != 0:
                return TaskPhase.FIXING

            # Check tool names & commands
            tool = str(payload.get("tool", "")).lower()
            cmd = str(payload.get("command", "") or payload.get("cmd", "") or payload.get("arguments", "")).lower()

            if "test" in tool or "pytest" in cmd or "test" in cmd:
                return TaskPhase.TESTING
            if "edit" in tool or "write" in tool or "replace" in tool:
                return TaskPhase.CODING
            if etype == StandardEventType.USER_PROMPT.value or "read" in tool or "find" in tool:
                return TaskPhase.PLANNING

        return TaskPhase.PLANNING

    def detect_stall_or_loop(
        self,
        session_id: str,
        loop_threshold: int = 3,
        failure_threshold: int = 3,
    ) -> StallDetectionResult:
        """Detect if agent is stuck in an error loop (e.g. repeated same failing command)."""
        events = self.store.query(session_id=session_id, limit=30, descending=True)
        if not events:
            return StallDetectionResult()

        tool_events = [
            e for e in events
            if (isinstance(e.type, str) and "tool_call" in e.type)
            or (hasattr(e.type, "value") and "tool_call" in e.type.value)
        ]

        if not tool_events:
            return StallDetectionResult()

        # 1. Check consecutive failures
        consecutive_failures = 0
        for e in tool_events:
            payload = e.payload or {}
            etype = e.type if isinstance(e.type, str) else e.type.value
            if etype == StandardEventType.TOOL_CALL_FAILED.value or payload.get("exit_code", 0) != 0:
                consecutive_failures += 1
            else:
                break

        # 2. Check recent identical failing commands
        recent_failed_cmds: list[str] = []
        for e in tool_events[:10]:
            payload = e.payload or {}
            etype = e.type if isinstance(e.type, str) else e.type.value
            if etype == StandardEventType.TOOL_CALL_FAILED.value or payload.get("exit_code", 0) != 0:
                args = str(payload.get("command") or payload.get("arguments") or payload.get("cmd") or "")
                if args:
                    recent_failed_cmds.append(args.strip())

        counts = Counter(recent_failed_cmds)
        most_common_cmd, most_common_count = counts.most_common(1)[0] if counts else ("", 0)

        is_loop = most_common_count >= loop_threshold
        is_stalled = consecutive_failures >= failure_threshold or is_loop

        warning = ""
        if is_loop:
            warning = f"Command loop detected: '{most_common_cmd[:80]}' failed {most_common_count} times."
        elif is_stalled:
            warning = f"Agent stall detected: {consecutive_failures} consecutive tool failures."

        return StallDetectionResult(
            is_stalled=is_stalled,
            is_looping=is_loop,
            repeated_command=most_common_cmd,
            repeat_count=most_common_count,
            consecutive_failures=consecutive_failures,
            warning=warning,
        )
