from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typesafe import Choice, Noul, Score, ask


class FakeClient:
    last: FakeClient | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeClient.last = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def system_one(self, state, questions, **kwargs):
        self.questions = questions
        return SimpleNamespace(
            choices={"tone": SimpleNamespace(choice="angry")},
            scores={"urgency": SimpleNamespace(score=2.0)},
            nouls={"billing": SimpleNamespace(noul=0.9)},
        )


class TypeSafeTest(unittest.TestCase):
    def test_ask_uses_sdk(self):
        with patch("typesafe.TypeSafeClient", side_effect=FakeClient):
            out = ask(
                {"document": "charged twice ASAP"},
                {
                    "billing": Noul(instructions="billing?"),
                    "tone": Choice(instructions="tone?", criteria={"calm": None, "angry": None}),
                    "urgency": Score(instructions="urgency?", criteria=["wait", "today"]),
                },
                api_key="k",
            )
        fake = FakeClient.last
        assert fake is not None
        self.assertEqual(fake.kwargs["api_key"], "k")
        self.assertEqual(out.nouls["billing"].noul, 0.9)
        self.assertEqual(out.choices["tone"].choice, "angry")
        self.assertEqual(out.scores["urgency"].score, 2.0)
        self.assertIsInstance(fake.questions["billing"], Noul)


if __name__ == "__main__":
    unittest.main()
