from __future__ import annotations

import json
import unittest

import httpx

from local_agent.models.openai_compatible import OpenAICompatibleClient, responses_to_chat
from local_agent.models.qwen import qwen_client


class ClientTest(unittest.TestCase):
    def test_chat_completions(self):
        payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertTrue(str(request.url).endswith("/chat/completions"))
            body = json.loads(request.content)
            self.assertEqual(body["model"], "qwen3-coder")
            return httpx.Response(200, json=payload)

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAICompatibleClient(
            "http://127.0.0.1:8000/v1", "qwen3-coder", http=http, api="chat"
        )
        out = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out["choices"][0]["message"]["content"], "ok")

    def test_responses_maps_function_call(self):
        raw = {
            "id": "resp_1",
            "model": "DeepSeek-V4-Pro-Qwen3.5-9B",
            "output": [
                {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "think"}]},
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "write_file",
                    "arguments": '{"path":"hello.py","content":"x"}',
                },
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertTrue(str(request.url).endswith("/responses"))
            self.assertNotIn("Authorization", request.headers)
            body = json.loads(request.content)
            self.assertEqual(body["model"], "DeepSeek-V4-Pro-Qwen3.5-9B")
            self.assertEqual(body["tools"][0]["name"], "write_file")
            return httpx.Response(200, json=raw)

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAICompatibleClient(
            "http://192.168.7.182:18080/v1",
            "DeepSeek-V4-Pro-Qwen3.5-9B",
            http=http,
        )
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "write",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        out = client.chat([{"role": "user", "content": "write hello"}], tools=tools)
        tc = out["choices"][0]["message"]["tool_calls"][0]
        self.assertEqual(tc["function"]["name"], "write_file")

    def test_responses_to_chat_text(self):
        chat = responses_to_chat(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "pong"}],
                    }
                ]
            }
        )
        self.assertEqual(chat["choices"][0]["message"]["content"], "pong")

    def test_chat_sends_bearer(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "Bearer sk-test")
            self.assertTrue(str(request.url).endswith("/chat/completions"))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAICompatibleClient(
            "https://open.bigmodel.cn/api/coding/paas/v4",
            "glm-4-flash-250414",
            http=http,
            api="chat",
            api_key="sk-test",
        )
        out = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out["choices"][0]["message"]["content"], "ok")

    def test_default_client_from_config(self):
        c = qwen_client()
        self.assertEqual(c.endpoint, "http://192.168.7.182:18080/v1")
        self.assertEqual(c.model, "DeepSeek-V4-Pro-Qwen3.5-9B")
        self.assertEqual(c.api, "responses")


if __name__ == "__main__":
    unittest.main()
