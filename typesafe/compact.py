"""Drop stale tool calls/results via Jev nouls. Never summarize.

Port of https://github.com/tamaratran/fast-jev-compaction (keep / truncate / drop).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

try:
    from typesafe_sdk import Noul
except ImportError:
    class Noul:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.instructions = kwargs.get("instructions", "")


Asker = Callable[[str, dict[str, Any]], Any]

KEEP = 0.5
PRESERVE = 6
HEAD = 300


def _noul(resp: Any, key: str) -> float:
    nouls = getattr(resp, "nouls", None)
    if nouls is not None:
        a = nouls.get(key)
        if a is not None:
            return float(getattr(a, "noul", 0) or 0)
    answers = resp.get("answers") if isinstance(resp, dict) else None
    if isinstance(answers, dict):
        return float((answers.get(key) or {}).get("noul") or 0)
    return 0.0


def _pairs(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for i, m in enumerate(history):
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                tid = str(tc.get("id") or "")
                if not tid:
                    continue
                fn = tc.get("function") or {}
                by_id[tid] = {
                    "id": tid,
                    "msg_i": i,
                    "name": fn.get("name") or "",
                    "args": str(fn.get("arguments") or "")[:200],
                }
        elif m.get("role") == "tool":
            tid = str(m.get("tool_call_id") or "")
            if tid in by_id:
                by_id[tid]["res_i"] = i
                by_id[tid]["chars"] = len(m.get("content") or "")
    return [p for p in by_id.values() if "res_i" in p]


def _pinned(n: int, preserve: int) -> set[int]:
    pin = set(range(max(0, n - preserve), n))
    if n:
        pin.add(0)
    return pin


def _state(history: list[dict[str, Any]], goal: str) -> str:
    lines = [f"goal: {goal}"]
    for m in history:
        role = m.get("role")
        if role == "tool":
            c = m.get("content") or ""
            lines.append(f"tool_result {m.get('tool_call_id')}: ok, {len(c)} chars (omitted)")
        elif role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                lines.append(
                    f"tool_call {tc.get('id')} {fn.get('name')} {str(fn.get('arguments') or '')[:200]}"
                )
            if m.get("content"):
                lines.append(f"assistant: {str(m['content'])[:400]}")
        else:
            lines.append(f"{role}: {str(m.get('content') or '')[:400]}")
    return "\n".join(lines)


def _apply(
    history: list[dict[str, Any]],
    drop_call: set[str],
    drop_result: set[str],
    head: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in history:
        role = m.get("role")
        if role == "tool":
            tid = str(m.get("tool_call_id") or "")
            if tid in drop_call:
                continue
            if tid in drop_result:
                c = m.get("content") or ""
                if len(c) > head + 80:
                    nm = dict(m)
                    nm["content"] = (
                        c[:head]
                        + f"\n[truncated {len(c) - head} chars; re-run the tool if needed]"
                    )
                    out.append(nm)
                    continue
            out.append(m)
            continue
        if role == "assistant" and m.get("tool_calls"):
            tcs = [tc for tc in m["tool_calls"] if str(tc.get("id") or "") not in drop_call]
            if not tcs and not str(m.get("content") or "").strip():
                continue
            if tcs != m["tool_calls"]:
                nm = dict(m)
                if tcs:
                    nm["tool_calls"] = tcs
                else:
                    nm.pop("tool_calls", None)
                out.append(nm)
            else:
                out.append(m)
            continue
        out.append(m)
    return out


def compact_history(
    history: list[dict[str, Any]],
    goal: str = "",
    asker: Asker | None = None,
    *,
    keep_threshold: float = KEEP,
    preserve_recent: int = PRESERVE,
    truncate_head: int = HEAD,
) -> list[dict[str, Any]]:
    if len(history) <= preserve_recent + 1:
        return history
    pin = _pinned(len(history), preserve_recent)
    cands = [p for p in _pairs(history) if p["msg_i"] not in pin and p["res_i"] not in pin]
    if not cands:
        return history
    if asker is None:
        if os.environ.get("PYTEST_CURRENT_TEST") or not os.environ.get("TYPESAFE_API_KEY"):
            return history
        if os.environ.get("JEV_COMPACT", "1").strip().lower() in ("0", "false", "no"):
            return history
        from typesafe import ask as _ask

        asker = _ask
    questions = {}
    for i, p in enumerate(cands):
        questions[f"call_{i}"] = Noul(
            instructions=(
                f"Tool call {p['id']} ({p['name']}) should stay: knowing this call was made, "
                f"with its input, still matters for what the assistant does next. input={p['args']}"
            )
        )
        questions[f"result_{i}"] = Noul(
            instructions=(
                f"The full output of tool call {p['id']} ({p['name']}, {p['chars']} chars) "
                "should stay verbatim: the assistant still needs its contents and re-running "
                "the tool would not do"
            )
        )
    try:
        resp = asker(_state(history, goal), questions)
    except Exception:
        return history
    drop_call: set[str] = set()
    drop_result: set[str] = set()
    for i, p in enumerate(cands):
        kr = _noul(resp, f"result_{i}")
        kc = _noul(resp, f"call_{i}")
        if kr >= keep_threshold:
            continue
        if kc >= keep_threshold:
            drop_result.add(p["id"])
        else:
            drop_call.add(p["id"])
    if not drop_call and not drop_result:
        return history
    return _apply(history, drop_call, drop_result, truncate_head)
