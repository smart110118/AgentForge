"""Usage Engine: tracks token consumption, velocity, cost accrual, and context window forecasting."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from local_agent.events.schema import StandardAgentEvent, StandardEventType
from local_agent.events.store import EventStore


@dataclass
class ModelPricing:
    """Pricing in USD per million tokens."""
    prompt_per_m: float = 3.00        # default $3/1M
    completion_per_m: float = 15.00   # default $15/1M
    cached_prompt_per_m: float = 0.75 # default $0.75/1M cached (75% off)


@dataclass
class UsageSummary:
    session_id: str
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost_usd: float = 0.0
    token_velocity_per_minute: float = 0.0
    latest_event_timestamp: float = 0.0
    calls_count: int = 0


class UsageEngine:
    """Calculates real-time token metrics, velocity, cost, and forecasts window depletion."""

    DEFAULT_PRICING: dict[str, ModelPricing] = {
        "gpt-4o": ModelPricing(prompt_per_m=2.50, completion_per_m=10.00, cached_prompt_per_m=1.25),
        "claude-3-5-sonnet": ModelPricing(prompt_per_m=3.00, completion_per_m=15.00, cached_prompt_per_m=0.30),
        "deepseek-coder": ModelPricing(prompt_per_m=0.14, completion_per_m=0.28, cached_prompt_per_m=0.014),
        "default": ModelPricing(prompt_per_m=3.00, completion_per_m=15.00, cached_prompt_per_m=0.75),
    }

    def __init__(
        self,
        store: EventStore,
        pricing: dict[str, ModelPricing] | None = None,
        velocity_window_seconds: float = 300.0,  # 5 minute window for velocity
    ) -> None:
        self.store = store
        self.pricing = pricing or self.DEFAULT_PRICING
        self.velocity_window_seconds = velocity_window_seconds

    def _get_pricing_for_model(self, model: str) -> ModelPricing:
        for k, v in self.pricing.items():
            if k in model.lower():
                return v
        return self.pricing.get("default", ModelPricing())

    def get_summary(self, session_id: str) -> UsageSummary:
        """Compute aggregate usage summary for a session."""
        events = self.store.query(
            session_id=session_id,
            event_type=StandardEventType.USAGE_METRIC.value,
            limit=5000,
            descending=False,
        )

        summary = UsageSummary(session_id=session_id)
        if not events:
            return summary

        window_tokens = 0
        window_start = max(0.0, events[-1].timestamp - self.velocity_window_seconds)

        for e in events:
            payload = e.payload or {}
            usage = payload.get("usage", {})
            model = payload.get("model", "default")
            p_tokens = int(usage.get("prompt_tokens") or 0)
            c_tokens = int(usage.get("completion_tokens") or 0)
            t_tokens = int(usage.get("total_tokens") or (p_tokens + c_tokens))
            cached = int(usage.get("cached_tokens") or 0)

            summary.total_prompt_tokens += p_tokens
            summary.total_completion_tokens += c_tokens
            summary.total_tokens += t_tokens
            summary.cached_tokens += cached
            summary.calls_count += 1
            summary.latest_event_timestamp = max(summary.latest_event_timestamp, e.timestamp)

            # Pricing calculation
            mp = self._get_pricing_for_model(model)
            uncached_prompt = max(0, p_tokens - cached)
            cost = (
                (uncached_prompt * mp.prompt_per_m / 1_000_000.0)
                + (cached * mp.cached_prompt_per_m / 1_000_000.0)
                + (c_tokens * mp.completion_per_m / 1_000_000.0)
            )
            summary.estimated_cost_usd += cost

            # Velocity window accumulation
            if e.timestamp >= window_start:
                window_tokens += t_tokens

        # Token velocity (Tokens per minute)
        elapsed_sec = max(1.0, events[-1].timestamp - events[0].timestamp)
        effective_window = min(elapsed_sec, self.velocity_window_seconds)
        summary.token_velocity_per_minute = round((window_tokens / effective_window) * 60.0, 2)
        summary.estimated_cost_usd = round(summary.estimated_cost_usd, 6)
        return summary

    def forecast(
        self,
        session_id: str,
        context_window_limit: int = 128_000,
        current_context_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Forecast remaining context headroom and estimated time until context overflow."""
        summary = self.get_summary(session_id)
        current_tokens = current_context_tokens if current_context_tokens is not None else summary.total_tokens
        remaining_tokens = max(0, context_window_limit - current_tokens)
        ratio = current_tokens / context_window_limit if context_window_limit > 0 else 1.0

        time_to_exhaustion_min: float | None = None
        if summary.token_velocity_per_minute > 0 and remaining_tokens > 0:
            time_to_exhaustion_min = round(remaining_tokens / summary.token_velocity_per_minute, 2)

        return {
            "session_id": session_id,
            "context_window_limit": context_window_limit,
            "current_tokens": current_tokens,
            "remaining_tokens": remaining_tokens,
            "usage_ratio": round(ratio, 4),
            "token_velocity_per_minute": summary.token_velocity_per_minute,
            "estimated_minutes_remaining": time_to_exhaustion_min,
            "estimated_cost_usd": summary.estimated_cost_usd,
        }
