"""Budget Controller: dynamically regulates context compression and enforces budget policies."""

from __future__ import annotations

from typing import Any

from local_agent.analysis.task_engine import TaskEngine
from local_agent.analysis.usage_engine import UsageEngine
from local_agent.budget.policy import BudgetStatus, CompressionAction, PolicyDecision


class BudgetController:
    """Evaluates session budget health against model context window and cost quotas,
    determining the compression action according to the Policy Matrix.
    """

    def __init__(
        self,
        usage_engine: UsageEngine,
        task_engine: TaskEngine | None = None,
        context_window_limit: int = 128_000,
        cost_quota_usd: float = 10.0,
        threshold_yellow: float = 0.50,  # Below 50% headroom triggers YELLOW
        threshold_orange: float = 0.25,  # Below 25% headroom triggers ORANGE
        threshold_red: float = 0.10,     # Below 10% headroom triggers RED
    ) -> None:
        self.usage_engine = usage_engine
        self.task_engine = task_engine
        self.context_window_limit = context_window_limit
        self.cost_quota_usd = cost_quota_usd
        self.threshold_yellow = threshold_yellow
        self.threshold_orange = threshold_orange
        self.threshold_red = threshold_red

    def evaluate(
        self,
        session_id: str,
        current_context_tokens: int | None = None,
    ) -> PolicyDecision:
        """Evaluate session health and return policy decision according to Policy Matrix."""
        forecast = self.usage_engine.forecast(
            session_id=session_id,
            context_window_limit=self.context_window_limit,
            current_context_tokens=current_context_tokens,
        )

        remaining_tokens = forecast["remaining_tokens"]
        remaining_ratio = max(0.0, 1.0 - forecast["usage_ratio"])
        spent_cost = forecast["estimated_cost_usd"]
        cost_exceeded = spent_cost >= self.cost_quota_usd

        # Determine Budget Status
        if cost_exceeded or remaining_ratio < self.threshold_red:
            status = BudgetStatus.RED
            action = CompressionAction.HANDOFF_REQUIRED
            warning = f"Budget critical! Remaining headroom: {remaining_ratio*100:.1f}%, cost: ${spent_cost:.3f}/${self.cost_quota_usd:.2f}."
        elif remaining_ratio < self.threshold_orange:
            status = BudgetStatus.ORANGE
            action = CompressionAction.SUMMARIZATION
            warning = f"Budget low ({remaining_ratio*100:.1f}% remaining). Switching to semantic summarization."
        elif remaining_ratio < self.threshold_yellow:
            status = BudgetStatus.YELLOW
            action = CompressionAction.EXTRACTIVE
            warning = f"Budget tightening ({remaining_ratio*100:.1f}% remaining). Enabling extractive AST compression."
        else:
            status = BudgetStatus.GREEN
            action = CompressionAction.PASSTHROUGH
            warning = ""

        # Check if task engine detects loop/stall and append warning
        if self.task_engine:
            stall_info = self.task_engine.detect_stall_or_loop(session_id)
            if stall_info.is_stalled:
                warning += f" [STALL ALERT: {stall_info.warning}]"

        return PolicyDecision(
            status=status,
            action=action,
            remaining_ratio=round(remaining_ratio, 4),
            remaining_tokens=remaining_tokens,
            estimated_cost_usd=spent_cost,
            cost_exceeded=cost_exceeded,
            warning=warning.strip(),
        )
