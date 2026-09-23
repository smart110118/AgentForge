import pytest
from pathlib import Path

from local_agent.events import EventStore, StandardEventType
from local_agent.handoff import (
    FeedbackLoop,
    HandoffEngine,
    PromptProtocol,
    TargetAgentProfile,
    TargetExecutionResult,
)
from local_agent.transformation import ContextPackage, ContextPackageBuilder


def test_handoff_engine_profile_and_payload_adaptation(tmp_path: Path):
    store = EventStore(":memory:")
    builder = ContextPackageBuilder(workspace=tmp_path, store=store)
    pkg = builder.build(session_id="sess_ho_1", reason="Refactoring test modules")

    engine = HandoffEngine(store=store)

    # 1. Local Agent protocol payload
    local_ho = engine.prepare_handoff(pkg, target_agent_id="local_executor", task_instruction="Run tests and fix")
    assert local_ho.protocol == PromptProtocol.LOCAL_AGENT
    assert isinstance(local_ho.formatted_context, dict)
    assert "task" in local_ho.formatted_context
    assert local_ho.metadata["package_id"] == pkg.package_id

    # 2. Claude XML protocol payload
    claude_ho = engine.prepare_handoff(pkg, target_agent_id="claude_specialist", task_instruction="Review architecture")
    assert claude_ho.protocol == PromptProtocol.CLAUDE_XML
    assert isinstance(claude_ho.formatted_context, str)
    assert "<context_package" in claude_ho.formatted_context
    assert "<git_diff>" in claude_ho.formatted_context

    # 3. Verify event recorded in EventStore
    events = store.query(event_type=StandardEventType.HANDOFF_TRIGGERED.value)
    assert len(events) >= 2


def test_feedback_loop_closed_loop_recording():
    store = EventStore(":memory:")
    loop = FeedbackLoop(store=store)

    exec_result = TargetExecutionResult(
        handoff_id="ho_pkg_12345",
        target_agent_id="local_executor",
        status="completed",
        exit_code=0,
        tests_passed=12,
        tests_failed=0,
        files_changed=["local_agent/events/store.py"],
        summary="All tests passed and code committed cleanly.",
        correlation_id="trace_session_999",
        execution_duration_sec=3.45,
    )

    evt = loop.ingest_feedback(exec_result)

    assert evt is not None
    assert evt.type == StandardEventType.TOOL_CALL_COMPLETE
    assert evt.confidence == 0.99
    assert evt.payload["status"] == "completed"
    assert evt.payload["tests"]["passed"] == 12
    assert evt.payload["duration_sec"] == 3.45
    assert store.count() == 1

    # Verify queryable from store
    stored = store.query(session_id="ho_pkg_12345")
    assert len(stored) == 1
    assert stored[0].payload["files_changed"] == ["local_agent/events/store.py"]


def test_feedback_loop_failure_recording():
    store = EventStore(":memory:")
    loop = FeedbackLoop(store=store)

    exec_result = TargetExecutionResult(
        handoff_id="ho_pkg_failed",
        target_agent_id="local_executor",
        status="failed",
        exit_code=1,
        tests_passed=5,
        tests_failed=2,
        error="AssertionError in test_auth.py: line 42",
        correlation_id="trace_session_fail",
    )

    evt = loop.ingest_feedback(exec_result)
    assert evt.type == StandardEventType.TOOL_CALL_FAILED
    assert evt.payload["error"] == "AssertionError in test_auth.py: line 42"
    assert evt.payload["tests"]["failed"] == 2
