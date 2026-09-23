import time
import pytest
from pathlib import Path

from local_agent.analysis import (
    ModelPricing,
    StallDetectionResult,
    TaskEngine,
    TaskPhase,
    UsageEngine,
    UsageSummary,
)
from local_agent.budget import (
    BudgetController,
    BudgetStatus,
    CompressionAction,
    PolicyDecision,
)
from local_agent.events import (
    EventClient,
    EventGateway,
    EventSource,
    EventStore,
    NetworkObserver,
    StandardAgentEvent,
    StandardEventType,
)


@pytest.fixture
def store():
    return EventStore(":memory:")


def test_usage_engine_metrics_and_forecast(store):
    gw = EventGateway(store=store)
    net_obs = NetworkObserver(gateway=gw, client=EventClient.CURSOR, session_id="sess_budget_1")

    # Ingest 3 usage metric events over time
    net_obs.record_response(
        model="gpt-4o",
        usage={"prompt_tokens": 10_000, "completion_tokens": 2_000, "total_tokens": 12_000},
        latency_ms=500.0,
    )
    net_obs.record_response(
        model="gpt-4o",
        usage={"prompt_tokens": 20_000, "completion_tokens": 5_000, "total_tokens": 25_000},
        latency_ms=800.0,
    )

    usage_engine = UsageEngine(store=store)
    summary = usage_engine.get_summary("sess_budget_1")

    assert summary.total_prompt_tokens == 30_000
    assert summary.total_completion_tokens == 7_000
    assert summary.total_tokens == 37_000
    assert summary.calls_count == 2
    assert summary.estimated_cost_usd > 0

    # Test forecast
    fc = usage_engine.forecast("sess_budget_1", context_window_limit=100_000)
    assert fc["remaining_tokens"] == 63_000
    assert fc["usage_ratio"] == 0.37


def test_task_engine_phase_and_stall_detection(store):
    task_engine = TaskEngine(store=store)
    sess_id = "sess_task_1"

    # 1. Initially idle
    assert task_engine.infer_phase(sess_id) == TaskPhase.IDLE

    # 2. Add prompt -> Planning
    store.append(
        StandardAgentEvent(
            source=EventSource(session_id=sess_id),
            type=StandardEventType.USER_PROMPT,
            payload={"prompt": "Investigate repo"},
        )
    )
    assert task_engine.infer_phase(sess_id) == TaskPhase.PLANNING

    # 3. Add pytest command -> Testing
    store.append(
        StandardAgentEvent(
            source=EventSource(session_id=sess_id),
            type=StandardEventType.TOOL_CALL_COMPLETE,
            payload={"tool": "bash", "command": "pytest tests/test_foo.py", "exit_code": 0},
        )
    )
    assert task_engine.infer_phase(sess_id) == TaskPhase.TESTING

    # 4. Repeat failed command 3 times -> Detect Loop
    for _ in range(3):
        store.append(
            StandardAgentEvent(
                source=EventSource(session_id=sess_id),
                type=StandardEventType.TOOL_CALL_FAILED,
                payload={"tool": "bash", "command": "python broken.py", "exit_code": 1},
            )
        )

    assert task_engine.infer_phase(sess_id) == TaskPhase.FIXING
    stall_res = task_engine.detect_stall_or_loop(sess_id)
    assert stall_res.is_stalled is True
    assert stall_res.is_looping is True
    assert stall_res.repeated_command == "python broken.py"
    assert stall_res.repeat_count == 3


def test_budget_controller_policy_transitions(store):
    usage_engine = UsageEngine(store=store)
    task_engine = TaskEngine(store=store)
    controller = BudgetController(
        usage_engine=usage_engine,
        task_engine=task_engine,
        context_window_limit=100_000,
        cost_quota_usd=5.0,
    )
    sess_id = "sess_policy_1"

    # Case 1: Green (> 50% headroom remaining)
    dec_green = controller.evaluate(sess_id, current_context_tokens=30_000)
    assert dec_green.status == BudgetStatus.GREEN
    assert dec_green.action == CompressionAction.PASSTHROUGH
    assert dec_green.remaining_ratio == 0.70

    # Case 2: Yellow (25% - 50% headroom remaining, e.g. 60k used -> 40% remaining)
    dec_yellow = controller.evaluate(sess_id, current_context_tokens=60_000)
    assert dec_yellow.status == BudgetStatus.YELLOW
    assert dec_yellow.action == CompressionAction.EXTRACTIVE
    assert dec_yellow.remaining_ratio == 0.40

    # Case 3: Orange (10% - 25% headroom remaining, e.g. 80k used -> 20% remaining)
    dec_orange = controller.evaluate(sess_id, current_context_tokens=80_000)
    assert dec_orange.status == BudgetStatus.ORANGE
    assert dec_orange.action == CompressionAction.SUMMARIZATION
    assert dec_orange.remaining_ratio == 0.20

    # Case 4: Red (< 10% headroom remaining, e.g. 95k used -> 5% remaining)
    dec_red = controller.evaluate(sess_id, current_context_tokens=95_000)
    assert dec_red.status == BudgetStatus.RED
    assert dec_red.action == CompressionAction.HANDOFF_REQUIRED
    assert dec_red.remaining_ratio == 0.05
