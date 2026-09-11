from __future__ import annotations

import shlex
from pathlib import Path

from local_agent.config import load_config


class PolicyError(PermissionError):
    pass


def load_policy() -> dict:
    return load_config().get("policy") or {}


def check_shell(command: str) -> None:
    policy = load_policy().get("shell") or {}
    allow = set(policy.get("allow_binaries") or [])
    block = set(policy.get("block_tokens") or [])
    try:
        tokens = shlex.split(command)
    except ValueError as e:
        raise PolicyError(f"cannot parse command: {e}") from e
    if not tokens:
        raise PolicyError("empty command")
    binary = Path(tokens[0]).name
    if binary in block or binary in {t for t in tokens if t in block}:
        raise PolicyError(f"blocked command: {binary}")
    # also block if any token is a blocked binary name (e.g. `env rm -rf`)
    for tok in tokens:
        name = Path(tok).name
        if name in block:
            raise PolicyError(f"blocked token: {name}")
    if allow and binary not in allow:
        raise PolicyError(f"binary not in allowlist: {binary}")
