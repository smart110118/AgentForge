from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from local_agent.mcp.tools import execute
from local_agent.tools.tests import run_gate


def _load_task(raw: str) -> dict:
    path = Path(raw)
    if path.is_file():
        return json.loads(path.read_text())
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="local-agent")
    p.add_argument("--task", help="task JSON string or file path")
    p.add_argument("--wait", action="store_true", default=True)
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--gate", action="store_true", help="run deterministic gate only")
    p.add_argument("--workspace", default=".")
    p.add_argument("--test-command")
    p.add_argument("--mcp", action="store_true")
    args = p.parse_args(argv)

    if args.mcp:
        from local_agent.mcp.server import main as mcp_main

        mcp_main()
        return 0

    if args.gate:
        gate = run_gate(args.workspace, args.test_command)
        json.dump(gate, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if gate["ok"] else 1

    if not args.task:
        p.error("need --task, --gate, or --mcp")

    payload = _load_task(args.task)
    wait = False if args.no_wait else True
    result = execute(payload, wait=wait)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") in {"success", "running", "queued"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
