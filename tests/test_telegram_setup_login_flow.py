"""Regression: onboarding must not implicitly call Telethon.start()."""
import ast
from pathlib import Path
import unittest


class TelegramLoginFlowTests(unittest.TestCase):
    def test_delivery_helpers_show_fallback_without_exposing_hash(self):
        import telegram_setup

        from types import SimpleNamespace

        sent = SimpleNamespace(
            type=type("SentCodeTypeApp", (), {})(),
            next_type=type("CodeTypeSms", (), {})(),
            timeout=75,
            phone_code_hash="must-not-be-printed",
        )
        self.assertIn("служебный чат Telegram", telegram_setup.delivery_hint(sent))
        self.assertEqual(telegram_setup.next_delivery_hint(sent), "SMS")
        self.assertEqual(telegram_setup.delivery_timeout(sent), 75)
        self.assertNotIn(sent.phone_code_hash, telegram_setup.delivery_hint(sent))

    def test_resend_waits_for_telegram_timeout_before_request(self):
        import ast
        from pathlib import Path

        tree = ast.parse((Path(__file__).resolve().parents[1] / "telegram_setup.py").read_text(encoding="utf-8"))
        authorize = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "authorize")
        source = ast.unparse(authorize)
        self.assertLess(source.index("time.sleep(timeout)"), source.index("request_alternative_code(client, phone, sent)"))
        self.assertIn("if timeout:", source)

    def test_qr_login_is_available_without_phone_code_request(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "telegram_setup.py").read_text(encoding="utf-8"))
        auth = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "authorize")
        source = ast.unparse(auth)
        self.assertIn("await authorize_with_qr(client)", source)
        self.assertIn("Способ входа", source)
        self.assertIn("await client.send_code_request(phone)", source)

    def test_qr_flow_waits_for_scan_and_supports_two_step_password(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "telegram_setup.py").read_text(encoding="utf-8"))
        qr = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "authorize_with_qr")
        source = ast.unparse(qr)
        self.assertIn("await client.qr_login()", source)
        self.assertIn("await login.wait(timeout=120)", source)
        self.assertIn("SessionPasswordNeededError", source)
        self.assertIn("await client.sign_in(password=", source)

    def test_explicit_connect_precedes_phone_code_request(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "telegram_setup.py").read_text(encoding="utf-8"))
        auth = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "authorize")
        source = ast.unparse(auth)
        self.assertIn("await client.connect()", source)
        self.assertIn("await client.send_code_request(phone)", source)
        self.assertLess(source.index("await client.connect()"), source.index("await client.send_code_request(phone)"))
        self.assertNotIn("async with TelegramClient", source)
        self.assertIn("await client.disconnect()", source)


if __name__ == "__main__":
    unittest.main()
