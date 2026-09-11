from __future__ import annotations

import json
import unittest

import httpx

from local_agent.models.openai_compatible import OpenAICompatibleClient


class ClientTest(unittest.TestCase):
    def test_chat_completions(self):
        payload = {
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}}
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertTrue(str(request.url).endswith("/chat/completions"))
            body = json.loads(request.content)
            self.assertEqual(body["model"], "qwen3-coder")
            return httpx.Response(200, json=payload)

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAICompatibleClient("http://127.0.0.1:8000/v1", "qwen3-coder", http=http)
        out = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out["choices"][0]["message"]["content"], "ok")


if __name__ == "__main__":
    unittest.main()
