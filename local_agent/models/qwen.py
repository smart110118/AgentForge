from __future__ import annotations

from local_agent.config import load_config
from local_agent.models.openai_compatible import OpenAICompatibleClient


def qwen_client(cfg: dict | None = None) -> OpenAICompatibleClient:
    cfg = cfg or load_config()
    spec = cfg.get("executor") or cfg["models"]["qwen-coder"]
    timeout = float(cfg.get("agent", {}).get("timeout_seconds") or 180)
    return OpenAICompatibleClient(
        spec["endpoint"],
        spec["model"],
        timeout=timeout,
        api=str(spec.get("api") or "responses"),
        api_key=str(spec.get("api_key") or ""),
    )
