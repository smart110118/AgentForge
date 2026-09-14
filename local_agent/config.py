from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"

DEFAULTS = {
    "local": {
        "endpoint": "http://192.168.7.182:18080/v1",
        "model": "DeepSeek-V4-Pro-Qwen3.5-9B",
        "api": "responses",
    },
    "xai": {
        "endpoint": "https://api.x.ai/v1",
        "model": "grok-4.20-0309-reasoning",
        "api": "chat",
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api": "chat",
    },
}


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _load_dotenv() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def executor_spec(models: dict[str, Any] | None = None) -> dict[str, Any]:
    yaml_spec = dict((models or {}).get("qwen-coder") or {})
    provider = (os.environ.get("LLM_PROVIDER") or yaml_spec.get("provider") or "local").strip().lower()
    if provider in ("openai-compatible", "llama", "llamacpp"):
        provider = "local"
    api_override = os.environ.get("LOCAL_AGENT_API")
    temp = os.environ.get("LLM_TEMPERATURE")

    if provider == "xai":
        spec = {
            "provider": "xai",
            "endpoint": os.environ.get("XAI_BASE_URL") or DEFAULTS["xai"]["endpoint"],
            "model": os.environ.get("XAI_MODEL") or DEFAULTS["xai"]["model"],
            "api_key": os.environ.get("XAI_API_KEY") or "",
            "api": api_override or DEFAULTS["xai"]["api"],
        }
    elif provider == "openai":
        spec = {
            "provider": "openai",
            "endpoint": os.environ.get("OPENAI_BASE_URL") or DEFAULTS["openai"]["endpoint"],
            "model": os.environ.get("OPENAI_MODEL") or DEFAULTS["openai"]["model"],
            "api_key": os.environ.get("OPENAI_API_KEY") or "",
            "api": api_override or DEFAULTS["openai"]["api"],
        }
    else:
        spec = {
            "provider": "local",
            "endpoint": os.environ.get("LOCAL_AGENT_ENDPOINT")
            or yaml_spec.get("endpoint")
            or DEFAULTS["local"]["endpoint"],
            "model": os.environ.get("LOCAL_AGENT_MODEL")
            or yaml_spec.get("model")
            or DEFAULTS["local"]["model"],
            "api_key": os.environ.get("LOCAL_AGENT_API_KEY") or "",
            "api": api_override or yaml_spec.get("api") or DEFAULTS["local"]["api"],
        }
        if yaml_spec.get("n_ctx") is not None:
            spec["n_ctx"] = yaml_spec["n_ctx"]
    spec["endpoint"] = str(spec["endpoint"]).rstrip("/")
    spec["role"] = yaml_spec.get("role") or ["executor"]
    if temp:
        spec["temperature"] = float(temp)
    return spec


def load_config() -> dict[str, Any]:
    _load_dotenv()
    cfg = {
        "agent": _read_yaml(CONFIG_DIR / "agent.yaml").get("agent", {}),
        "models": _read_yaml(CONFIG_DIR / "models.yaml").get("models", {}),
        "policy": _read_yaml(CONFIG_DIR / "policy.yaml"),
    }
    spec = executor_spec(cfg["models"])
    cfg["models"]["qwen-coder"] = spec
    cfg["executor"] = spec
    if "temperature" in spec:
        cfg["agent"]["temperature"] = spec["temperature"]
    return cfg
