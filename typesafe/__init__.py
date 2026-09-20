"""Thin re-export of https://docs.typesafe.ai/sdk/python — not the executor LLM."""

from __future__ import annotations

from typing import Any

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
from typesafe.compact import compact_history

__all__ = ["Choice", "Noul", "Score", "TypeSafeClient", "ask", "compact_history"]


def ask(state: Any, questions: dict[str, Any], **kwargs: Any):
    client_kw = {k: kwargs.pop(k) for k in ("api_key", "base_url", "model") if k in kwargs}
    with TypeSafeClient(**client_kw) as client:
        return client.system_one(state=state, questions=questions, **kwargs)
