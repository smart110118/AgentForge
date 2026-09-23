"""Thin re-export of https://docs.typesafe.ai/sdk/python — not the executor LLM."""

from __future__ import annotations

from typing import Any

try:
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
except ImportError:
    class Choice:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class Noul:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class Score:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class TypeSafeClient:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass
        def __enter__(self) -> "TypeSafeClient":
            return self
        def __exit__(self, *args: Any) -> None:
            pass
        def system_one(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

from typesafe.compact import compact_history

__all__ = ["Choice", "Noul", "Score", "TypeSafeClient", "ask", "compact_history"]


def ask(state: Any, questions: dict[str, Any], **kwargs: Any):
    client_kw = {k: kwargs.pop(k) for k in ("api_key", "base_url", "model") if k in kwargs}
    with TypeSafeClient(**client_kw) as client:
        return client.system_one(state=state, questions=questions, **kwargs)
