"""Regression: onboarding must not implicitly call Telethon.start()."""
import ast
from pathlib import Path
import unittest


class TelegramLoginFlowTests(unittest.TestCase):
    def test_explicit_connect_precedes_phone_code_request(self):
        tree = ast.parse((Path(__file__).parent / "telegram_setup.py").read_text(encoding="utf-8"))
        auth = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "authorize")
        source = ast.unparse(auth)
        self.assertIn("await client.connect()", source)
        self.assertIn("await client.send_code_request(phone)", source)
        self.assertLess(source.index("await client.connect()"), source.index("await client.send_code_request(phone)"))
        self.assertNotIn("async with TelegramClient", source)
        self.assertIn("await client.disconnect()", source)


if __name__ == "__main__":
    unittest.main()
