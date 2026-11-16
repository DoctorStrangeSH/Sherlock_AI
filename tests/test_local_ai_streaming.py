"""Regression tests for local Ollama streaming and performance profiles."""
import json
import unittest
from unittest.mock import patch

import local_ai


class FakeResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


class LocalAiStreamingTests(unittest.TestCase):
    def test_streamed_chunks_are_joined_and_delivered(self):
        captured = []
        chunks = [
            b'{"message":{"content":"Hello"},"done":false}\n',
            b'{"message":{"content":" world"},"done":false}\n',
            b'{"done":true}\n',
        ]
        with patch.object(local_ai.urllib.request, "urlopen", return_value=FakeResponse(chunks)) as urlopen:
            result = local_ai._request("Hi", model="qwen3:1.7b", performance="Быстро",
                                       on_chunk=captured.append)
        self.assertEqual(result, "Hello world")
        self.assertEqual(captured, ["Hello", " world"])
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["model"], "qwen3:1.7b")
        self.assertTrue(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 160)
        self.assertEqual(payload["options"]["num_ctx"], 2048)

    def test_profile_falls_back_to_balanced(self):
        response = FakeResponse([])
        response.__iter__ = lambda: iter([])
        with patch.object(local_ai.urllib.request, "urlopen", return_value=response) as urlopen:
            local_ai._request("Hi", model="qwen3:1.7b", performance="invalid",
                              on_chunk=lambda _x: None)
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["options"]["num_predict"], 320)

    def test_stream_errors_are_not_silent(self):
        chunks = [b'{"error":"model failed"}\n']
        with patch.object(local_ai.urllib.request, "urlopen", return_value=FakeResponse(chunks)):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                local_ai._request("Hi", model="qwen3:1.7b", on_chunk=lambda _x: None)


if __name__ == "__main__":
    unittest.main()
