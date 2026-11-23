import asyncio
import io
import json
import unittest
from unittest.mock import patch

import chat_cli
import local_ai


class ChatFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_chat_uses_bounded_context(self):
        inputs = iter(["Привет", "Помнишь?", "/clear", "Снова", "/exit"])
        outputs = []
        seen = []

        async def fake_ai(question, history):
            seen.append((question, list(history)))
            return "Ответ " + question

        with patch.object(chat_cli, "ask_local_ai", side_effect=fake_ai):
            await chat_cli.chat(lambda prompt: next(inputs), outputs.append)
        self.assertEqual(len(seen), 3)
        self.assertEqual(len(seen[0][1]), 0)
        self.assertEqual(len(seen[1][1]), 2)
        self.assertEqual(len(seen[2][1]), 0)
        self.assertTrue(any("До встречи" in output for output in outputs))

    async def test_unavailable_model_not_saved(self):
        inputs = iter(["Привет", "Снова", "/exit"])
        seen = []

        async def fake_ai(question, history):
            seen.append(list(history))
            return "Локальная модель недоступна. Проверь Ollama."

        with patch.object(chat_cli, "ask_local_ai", side_effect=fake_ai):
            await chat_cli.chat(lambda prompt: next(inputs), lambda text: None)
        self.assertEqual(seen, [[], []])


class OllamaPayloadTests(unittest.TestCase):
    def test_request_contains_context_without_telegram_secrets(self):
        captured = {}
        response = io.BytesIO('{"message":{"content":"Все хорошо!"}}'.encode("utf-8"))
        def open_request(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return response

        with patch.object(local_ai.urllib.request, "urlopen", side_effect=open_request), patch.object(local_ai, "selected_model", return_value="qwen3:8b"):
            answer = local_ai._request(
                "Что делать?",
                [{"role": "user", "content": "Привет"}],
                ["Люблю Godot"],
                "warm",
                ["Починить игру"],
            )
        self.assertEqual(answer, "Все хорошо!")
        self.assertEqual(captured["timeout"], 90)
        messages = captured["payload"]["messages"]
        self.assertEqual(messages[-1]["content"], "Что делать?")
        self.assertTrue(any("Люблю Godot" in msg["content"] for msg in messages))
        self.assertTrue(any("Починить игру" in msg["content"] for msg in messages))


if __name__ == "__main__":
    unittest.main()
