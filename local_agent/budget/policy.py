"""Budget policy definitions and threshold matrices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetStatus(str, Enum):
    GREEN = "green"    # > 50% headroom: abundant
    YELLOW = "yellow"  # 25% - 50% headroom: tightening
    ORANGE = "orange"  # 10% - 25% headroom: warning
    RED = "red"        # < 10% headroom: critical / exhaustion


class CompressionAction(str, Enum):
    PASSTHROUGH = "passthrough"          # Full context, no compression
    EXTRACTIVE = "extractive"            # Trim shell outputs, fold AST bodies
    SUMMARIZATION = "summarization"      # Semantic summary of trial-and-error, keep Git Diff only
    HANDOFF_REQUIRED = "handoff_required" # Context exhausted, hand off task to target agent


@dataclass
class PolicyDecision:
    status: BudgetStatus
    action: CompressionAction
    remaining_ratio: float
    remaining_tokens: int
    estimated_cost_usd: float
    cost_exceeded: bool
    warning: str = ""
