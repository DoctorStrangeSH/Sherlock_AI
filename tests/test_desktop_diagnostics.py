"""Privacy and rotation tests for local diagnostics."""
import json
import logging
import logging.handlers
import tempfile
import unittest
from pathlib import Path
import sys
import threading

from desktop_diagnostics import (
    MAX_LOG_BYTES, configure_diagnostics, install_exception_hooks,
    redact_sensitive_text, safe_exception_summary, shutdown_diagnostics,
    write_support_report,
)


class DesktopDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.original_sys_hook = sys.excepthook
        self.original_thread_hook = getattr(threading, "excepthook", None)
        self.logger = logging.getLogger("sherlock_ai")

    def tearDown(self):
        sys.excepthook = self.original_sys_hook
        if self.original_thread_hook is not None:
            threading.excepthook = self.original_thread_hook
        shutdown_diagnostics(self.logger)

    def test_redacts_credentials_and_user_paths(self):
        value = ("Authorization: Bearer abc.def.secret api_hash=0123456789abcdef "
                 "https://user:pass@example.test/path?token=private C:\\Users\\Alice\\data")
        redacted = redact_sensitive_text(value)
        for secret in ("abc.def.secret", "0123456789abcdef", "user:pass", "token=private", "Alice"):
            self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redacts_telegram_bot_tokens(self):
        value = "failed for token 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        self.assertNotIn("123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", redact_sensitive_text(value))

    def test_os_errors_do_not_expose_private_paths(self):
        summary = safe_exception_summary(FileNotFoundError("missing C:\\Users\\Alice\\Private\\taxes.pdf"))
        self.assertIn("FileNotFoundError", summary)
        self.assertNotIn("Alice", summary)
        self.assertNotIn("taxes.pdf", summary)

    def test_exception_summary_has_no_traceback(self):
        summary = safe_exception_summary(ValueError("api_key=secret-value"))
        self.assertIn("ValueError", summary)
        self.assertNotIn("secret-value", summary)
        self.assertNotIn("Traceback", summary)

    def test_configures_rotating_local_log_and_redacts_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            logger, path = configure_diagnostics(temp, app_version="test")
            logger.info("operation failed api_key=secret-value")
            for handler in logger.handlers:
                handler.flush()
            content = path.read_text(encoding="utf-8")
            self.assertIn("operation failed", content)
            self.assertNotIn("secret-value", content)
            self.assertTrue(path.parent.is_dir())
            self.assertTrue(any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers))
            shutdown_diagnostics(logger)

    def test_report_contains_only_metadata_and_sanitized_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log_path = root / "sherlock.log"
            log_path.write_text("INFO started\nERROR request api_key=super-secret\n", encoding="utf-8")
            target = write_support_report(root / "support.json", log_path, app_version="test")
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["application"]["version"], "test")
            self.assertFalse(report["privacy"]["chat_history_included"])
            self.assertFalse(report["privacy"]["prompts_and_model_output_included"])
            self.assertNotIn("super-secret", target.read_text(encoding="utf-8"))
            self.assertEqual(len(report["recent_logs"]), 2)

    def test_report_handles_missing_log(self):
        with tempfile.TemporaryDirectory() as temp:
            target = write_support_report(Path(temp) / "report.json", Path(temp) / "missing.log")
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["recent_logs"], [])

    def test_log_rotation_limits_file_size(self):
        with tempfile.TemporaryDirectory() as temp:
            logger, path = configure_diagnostics(temp)
            for index in range(1000):
                logger.info("diagnostic event %04d %s", index, "x" * 1200)
            for handler in logger.handlers:
                handler.flush()
            self.assertLessEqual(path.stat().st_size, MAX_LOG_BYTES)
            self.assertTrue(Path(str(path) + ".1").exists())
            shutdown_diagnostics(logger)

    def test_unavailable_log_storage_does_not_raise(self):
        from unittest.mock import patch
        with patch("desktop_diagnostics.diagnostics_directory", return_value=Path("blocked")):
            with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
                logger, log_path = configure_diagnostics()
        self.assertIsNone(log_path)
        self.assertTrue(logger.handlers)

    def test_exception_hooks_can_be_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            logger, _ = configure_diagnostics(temp)
            install_exception_hooks(logger)
            self.assertTrue(callable(sys.excepthook))
            if hasattr(threading, "excepthook"):
                self.assertTrue(callable(threading.excepthook))
            shutdown_diagnostics(logger)


if __name__ == "__main__":
    unittest.main()
