from __future__ import annotations

import os
import unittest

from local_agent.config import executor_spec, load_config


class ConfigTest(unittest.TestCase):
    def test_yaml_local_executor(self):
        spec = load_config()["models"]["qwen-coder"]
        self.assertEqual(spec["endpoint"], "http://192.168.7.182:18080/v1")
        self.assertEqual(spec["model"], "DeepSeek-V4-Pro-Qwen3.5-9B")
        self.assertEqual(spec["api"], "responses")
        self.assertEqual(spec.get("n_ctx"), 65536)

    def test_openai_glm(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_BASE_URL"] = "https://open.bigmodel.cn/api/coding/paas/v4"
        os.environ["OPENAI_MODEL"] = "glm-4-flash-250414"
        os.environ["LOCAL_AGENT_API"] = "chat"
        try:
            spec = executor_spec()
            self.assertEqual(spec["provider"], "openai")
            self.assertEqual(spec["model"], "glm-4-flash-250414")
            self.assertEqual(spec["api"], "chat")
            self.assertEqual(spec["api_key"], "sk-test")
        finally:
            for k in (
                "LLM_PROVIDER",
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "OPENAI_MODEL",
                "LOCAL_AGENT_API",
            ):
                os.environ.pop(k, None)

    def test_xai(self):
        os.environ["LLM_PROVIDER"] = "xai"
        os.environ["XAI_API_KEY"] = "xai-test"
        try:
            spec = executor_spec()
            self.assertEqual(spec["provider"], "xai")
            self.assertTrue(spec["endpoint"].startswith("https://api.x.ai"))
            self.assertEqual(spec["api"], "chat")
            self.assertEqual(spec["api_key"], "xai-test")
        finally:
            os.environ.pop("LLM_PROVIDER", None)
            os.environ.pop("XAI_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
