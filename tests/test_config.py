from __future__ import annotations

import unittest

from local_agent.config import load_config


class ConfigTest(unittest.TestCase):
    def test_qwen_endpoint(self):
        cfg = load_config()
        self.assertEqual(cfg["models"]["qwen-coder"]["endpoint"], "http://127.0.0.1:8000/v1")


if __name__ == "__main__":
    unittest.main()
