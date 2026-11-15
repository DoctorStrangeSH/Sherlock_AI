"""Credential setup tests: no actual Telegram network or secrets."""
from pathlib import Path
import tempfile
import unittest

from run_local import load_local_environment
from telegram_setup import save_local_config


class LocalSetupTests(unittest.TestCase):
    def test_private_config_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            save_local_config({"TELEGRAM_API_ID": "123", "TELEGRAM_SESSION_STRING": "fake-local-token"}, target)
            self.assertEqual(
                load_local_environment(target, inherited={})["TELEGRAM_SESSION_STRING"],
                "fake-local-token"
            )
            with self.assertRaises(FileExistsError):
                save_local_config({"TELEGRAM_SESSION_STRING": "overwrite"}, target)
            self.assertIn("fake-local-token", target.read_text(encoding="utf-8"))

    def test_rejects_newlines_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            with self.assertRaises(ValueError):
                save_local_config({"TELEGRAM_SESSION_STRING": "secret\ninjected=true"}, target)
            self.assertFalse(target.exists())
            target.write_text("UNEXPECTED_KEY=test\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_local_environment(target, inherited={})

    def test_only_whitelisted_settings_are_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            target.write_text("# comment\nOLLAMA_MODEL=auto\n", encoding="utf-8")
            self.assertEqual(
                load_local_environment(target, inherited={}), {"OLLAMA_MODEL": "auto"}
            )


if __name__ == "__main__":
    unittest.main()
