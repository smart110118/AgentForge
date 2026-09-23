import time
import pytest
from pathlib import Path

from local_agent.events import (
    EventClient,
    EventGateway,
    EventSource,
    EventStore,
    LocalObserver,
    NetworkObserver,
    ObserverType,
    StandardAgentEvent,
    StandardEventType,
)


def test_sae_schema_serialization():
    source = EventSource(
        client=EventClient.CURSOR,
        observer=ObserverType.LOCAL,
        session_id="test_sess_1",
        host="localhost",
    )
    event = StandardAgentEvent(
        event_id="evt_test_1",
        timestamp=1000.0,
        source=source,
        type=StandardEventType.TOOL_CALL_COMPLETE,
        payload={"command": "pytest", "exit_code": 0},
        correlation_id="corr_123",
        confidence=0.95,
    )

    d = event.to_dict()
    assert d["event_id"] == "evt_test_1"
    assert d["source"]["client"] == "cursor"
    assert d["type"] == "tool_call.complete"
    assert d["confidence"] == 0.95

    restored = StandardAgentEvent.from_dict(d)
    assert restored.event_id == "evt_test_1"
    assert restored.source.client == "cursor"
    assert restored.payload["command"] == "pytest"


def test_event_store_crud(tmp_path: Path):
    db_file = tmp_path / "test_events.db"
    store = EventStore(db_file)

    assert store.count() == 0

    e1 = StandardAgentEvent(
        event_id="e1",
        timestamp=100.0,
        source=EventSource(client=EventClient.CURSOR, session_id="s1"),
        type=StandardEventType.USER_PROMPT,
        payload={"prompt": "hello"},
        correlation_id="c1",
    )
    e2 = StandardAgentEvent(
        event_id="e2",
        timestamp=105.0,
        source=EventSource(client=EventClient.CURSOR, session_id="s1"),
        type=StandardEventType.TOOL_CALL_COMPLETE,
        payload={"tool": "bash"},
        correlation_id="c1",
    )

    store.append_batch([e1, e2])
    assert store.count() == 2

    # Query by session
    results = store.query(session_id="s1")
    assert len(results) == 2
    assert results[0].event_id == "e1"
    assert results[1].event_id == "e2"

    # Query by time window
    results_window = store.query(start_ts=102.0)
    assert len(results_window) == 1
    assert results_window[0].event_id == "e2"


def test_gateway_deduplicate_and_correlate():
    store = EventStore(":memory:")
    gw = EventGateway(store=store, dedup_window_seconds=2.0)

    # Ingest first event
    e1 = gw.ingest(
        {
            "session_id": "sess_A",
            "type": StandardEventType.TOOL_CALL_COMPLETE,
            "payload": {"cmd": "git status"},
            "timestamp": 100.0,
        }
    )
    assert e1 is not None
    assert store.count() == 1
    assert e1.correlation_id.startswith("trace_sess_A")

    # Ingest identical event within deduplication window (should be dropped)
    e1_dup = gw.ingest(
        {
            "session_id": "sess_A",
            "type": StandardEventType.TOOL_CALL_COMPLETE,
            "payload": {"cmd": "git status"},
            "timestamp": 101.0,
        }
    )
    assert e1_dup is None
    assert store.count() == 1

    # Ingest a subsequent different event -> should link parent_event_id to e1
    e2 = gw.ingest(
        {
            "session_id": "sess_A",
            "type": StandardEventType.TOOL_CALL_COMPLETE,
            "payload": {"cmd": "git diff"},
            "timestamp": 102.0,
        }
    )
    assert e2 is not None
    assert store.count() == 2
    assert e2.parent_event_id == e1.event_id


def test_local_observer():
    store = EventStore(":memory:")
    gw = EventGateway(store=store)
    observer = LocalObserver(gateway=gw, client=EventClient.CURSOR, session_id="session_local")

    # 1. Prompt event
    p_evt = observer.record_user_prompt("Please run tests")
    assert p_evt is not None
    assert p_evt.type == StandardEventType.USER_PROMPT
    assert p_evt.payload["prompt"] == "Please run tests"

    # 2. Tool complete event
    t_evt = observer.record_tool_call(
        tool_name="bash",
        arguments={"command": "pytest"},
        result="5 passed",
        exit_code=0,
    )
    assert t_evt is not None
    assert t_evt.type == StandardEventType.TOOL_CALL_COMPLETE
    assert t_evt.payload["tool"] == "bash"
    assert t_evt.confidence == 0.85

    # 3. Tool failed event
    f_evt = observer.record_tool_call(
        tool_name="bash",
        arguments={"command": "pytest"},
        exit_code=1,
        error="assertion error",
    )
    assert f_evt is not None
    assert f_evt.type == StandardEventType.TOOL_CALL_FAILED
    assert f_evt.payload["exit_code"] == 1


def test_network_observer():
    store = EventStore(":memory:")
    gw = EventGateway(store=store)
    observer = NetworkObserver(gateway=gw, client=EventClient.CLAUDE_CODE, session_id="session_net")

    # Record API request
    req_evt = observer.record_request(model="claude-3-5-sonnet", messages_count=4)
    assert req_evt is not None
    assert req_evt.type == StandardEventType.API_REQUEST
    assert req_evt.payload["model"] == "claude-3-5-sonnet"

    # Record API response with token usage
    resp_evt = observer.parse_openai_response(
        response_json={
            "model": "claude-3-5-sonnet",
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165,
            },
        },
        latency_ms=350.5,
    )
    assert resp_evt is not None
    assert resp_evt.type == StandardEventType.USAGE_METRIC
    assert resp_evt.payload["usage"]["prompt_tokens"] == 120
    assert resp_evt.payload["usage"]["total_tokens"] == 165
    assert resp_evt.confidence == 0.90
