from __future__ import annotations

import unittest
from types import SimpleNamespace

from typesafe.compact import compact_history


def _hist() -> list[dict]:
    # 10 msgs; preserve=6 pins 0 and 4..9 so pair t1 at 2/3 is a candidate
    return [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "t0", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\":\"a\"}"}}
        ]},
        {"role": "tool", "tool_call_id": "t0", "content": "first"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "t1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\":\"old.py\"}"}}
        ]},
        {"role": "tool", "tool_call_id": "t1", "content": "STALE" * 200},
        {"role": "assistant", "content": "recent"},
        {"role": "user", "content": "u5"},
        {"role": "user", "content": "u6"},
        {"role": "user", "content": "u7"},
        {"role": "user", "content": "u8"},
        {"role": "user", "content": "u9"},
    ]


def _resp(call: float, result: float) -> SimpleNamespace:
    return SimpleNamespace(
        nouls={
            "call_0": SimpleNamespace(noul=call),
            "result_0": SimpleNamespace(noul=result),
        }
    )


class CompactTest(unittest.TestCase):
    def test_drop_call_removes_pair(self):
        out = compact_history(_hist(), "fix bug", asker=lambda s, q: _resp(0.1, 0.1))
        ids = [m.get("tool_call_id") or (m.get("tool_calls") or [{}])[0].get("id") for m in out]
        self.assertNotIn("t1", ids)
        self.assertIn("t0", ids)

    def test_drop_result_truncates(self):
        out = compact_history(_hist(), "fix bug", asker=lambda s, q: _resp(0.9, 0.1))
        tool = next(m for m in out if m.get("tool_call_id") == "t1")
        self.assertIn("truncated", tool["content"])
        self.assertLess(len(tool["content"]), 1000)

    def test_keep_both(self):
        src = _hist()
        out = compact_history(src, "fix bug", asker=lambda s, q: _resp(0.9, 0.9))
        self.assertEqual(len(out), len(src))

    def test_asker_error_keeps_history(self):
        src = _hist()

        def boom(s, q):
            raise RuntimeError("jev down")

        self.assertEqual(compact_history(src, "fix", asker=boom), src)


if __name__ == "__main__":
    unittest.main()
