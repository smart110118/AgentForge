#!/usr/bin/env python3
"""Cursor-side reminder only. Never emit followup_message (that re-enters the agent)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdin.read()
ws = os.environ.get("CURSOR_PROJECT_DIR") or os.getcwd()
note = (
    "Gateway owns git diff --check and test exit codes. "
    "Use local_agent_result; local_agent_retry if status is not success."
)
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from local_agent.tools.tests import run_gate

    gate = run_gate(ws, None)
    note += " git diff --check: " + ("ok" if gate.get("ok") else "fail")
except Exception as e:
    note += f" (gate skip: {e})"

print(json.dumps({"additional_context": note}))
