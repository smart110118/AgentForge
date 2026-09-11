from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict[str, Any]:
    cfg = {
        "agent": _read_yaml(CONFIG_DIR / "agent.yaml").get("agent", {}),
        "models": _read_yaml(CONFIG_DIR / "models.yaml").get("models", {}),
        "policy": _read_yaml(CONFIG_DIR / "policy.yaml"),
    }
    endpoint = os.environ.get("LOCAL_AGENT_ENDPOINT")
    model_name = os.environ.get("LOCAL_AGENT_MODEL")
    qwen = cfg["models"].setdefault("qwen-coder", {})
    if endpoint:
        qwen["endpoint"] = endpoint
    if model_name:
        qwen["model"] = model_name
    return cfg
