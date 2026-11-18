import io
import json
import unittest
from unittest.mock import patch

from doctor import check_environment, check_dependencies, check_ollama, main


class DoctorTests(unittest.TestCase):
    def test_missing_environment_never_echoes_secret_values(self):
        env = {
            "TELEGRAM_API_ID": "wrong",
            "TELEGRAM_API_HASH": "top-secret",
            "TELEGRAM_SESSION_STRING": "ultra-secret",
            "TELEGRAM_OWNER_ID": "-5",
            "TELEGRAM_GROUP_ID": "123",
        }
        errors = check_environment(env)
        report = " ".join(errors)
        self.assertIn("TELEGRAM_API_ID", report)
        self.assertIn("TELEGRAM_OWNER_ID", report)
        self.assertNotIn("top-secret", report)
        self.assertNotIn("ultra-secret", report)

    def test_environment_success(self):
        env = {key: "123" for key in (
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING",
            "TELEGRAM_OWNER_ID", "TELEGRAM_GROUP_ID"
        )}
        self.assertEqual(check_environment(env), [])

    def test_missing_dependencies(self):
        self.assertEqual(len(check_dependencies(lambda name: None)), 2)

    def test_ollama_model_present(self):
        payload = json.dumps({"models": [{"name": "qwen2.5:3b"}]}).encode()
        def opener(request, timeout):
            self.assertEqual(timeout, 3)
            return io.BytesIO(payload)
        self.assertEqual(check_ollama(model="qwen2.5:3b", opener=opener), [])

    def test_ollama_model_missing(self):
        def opener(request, timeout):
            return io.BytesIO(b'{"models":[]}')
        self.assertIn("ollama pull", check_ollama(model="qwen2.5:3b", opener=opener)[0])

    def test_invalid_command_line(self):
        with patch("builtins.print"):
            self.assertEqual(main(["--unknown"]), 2)


if __name__ == "__main__":
    unittest.main()
