"""Standard Agent Event (SAE) data contracts and schema definitions."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class EventClient(str, Enum):
    CURSOR = "cursor"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    LOCAL_AGENT = "local_agent"
    UNKNOWN = "unknown"


class ObserverType(str, Enum):
    NATIVE = "native_observer"
    LOCAL = "local_observer"
    RUNTIME = "runtime_observer"
    NETWORK = "network_observer"


class StandardEventType(str, Enum):
    # Prompt & User Interaction
    USER_PROMPT = "user.prompt"
    AGENT_THINKING = "agent.thinking"
    
    # Tool Execution
    TOOL_CALL_START = "tool_call.start"
    TOOL_CALL_COMPLETE = "tool_call.complete"
    TOOL_CALL_FAILED = "tool_call.failed"
    
    # Filesystem & OS Runtime
    FS_CHANGE = "runtime.fs_change"
    PROCESS_EXEC = "runtime.process_exec"
    
    # Network & Model Usage
    API_REQUEST = "network.api_request"
    API_RESPONSE = "network.api_response"
    USAGE_METRIC = "network.usage_metric"
    
    # System & Handoff
    HANDOFF_TRIGGERED = "handoff.triggered"
    GENERIC = "generic.event"


@dataclass
class EventSource:
    client: EventClient | str = EventClient.UNKNOWN
    observer: ObserverType | str = ObserverType.LOCAL
    session_id: str = ""
    host: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "client": str(self.client.value if isinstance(self.client, EventClient) else self.client),
            "observer": str(self.observer.value if isinstance(self.observer, ObserverType) else self.observer),
            "session_id": self.session_id,
            "host": self.host,
        }


@dataclass
class StandardAgentEvent:
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    timestamp: float = field(default_factory=time.time)
    source: EventSource = field(default_factory=EventSource)
    type: StandardEventType | str = StandardEventType.GENERIC
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    parent_event_id: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source.to_dict() if isinstance(self.source, EventSource) else self.source,
            "type": str(self.type.value if isinstance(self.type, StandardEventType) else self.type),
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StandardAgentEvent:
        source_data = data.get("source", {})
        if isinstance(source_data, dict):
            source = EventSource(
                client=source_data.get("client", EventClient.UNKNOWN),
                observer=source_data.get("observer", ObserverType.LOCAL),
                session_id=source_data.get("session_id", ""),
                host=source_data.get("host", ""),
            )
        else:
            source = EventSource()

        return cls(
            event_id=data.get("event_id", f"evt_{uuid.uuid4().hex}"),
            timestamp=float(data.get("timestamp", time.time())),
            source=source,
            type=data.get("type", StandardEventType.GENERIC),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id", ""),
            parent_event_id=data.get("parent_event_id", ""),
            confidence=float(data.get("confidence", 1.0)),
        )
