"""Auth failures have safe, actionable messages and never reveal exception details."""
import asyncio
import unittest

from telegram_setup import authorization_error_message


def fake_error(name, message="DO_NOT_LEAK_SESSION_SECRET", **attrs):
    cls = type(name, (Exception,), {})
    err = cls(message)
    for key, value in attrs.items():
        setattr(err, key, value)
    return err


class AuthErrorsTests(unittest.TestCase):
    def test_invalid_code_is_distinct_from_disconnected_network(self):
        invalid = authorization_error_message(fake_error("PhoneCodeInvalidError"))
        disconnected = authorization_error_message(asyncio.IncompleteReadError(b"", 8))
        self.assertIn("Код не подходит", invalid)
        self.assertIn("Соединение разорвалось", disconnected)
        self.assertNotEqual(invalid, disconnected)

    def test_expired_code_and_flood_wait(self):
        self.assertIn("истёк", authorization_error_message(fake_error("PhoneCodeExpiredError")))
        self.assertIn("120 секунд", authorization_error_message(fake_error("FloodWaitError", seconds=120)))

    def test_no_secrets_in_known_or_unknown_error_text(self):
        for name in ("PhoneCodeInvalidError", "PhoneCodeExpiredError", "PasswordHashInvalidError",
                     "FloodWaitError", "UnexpectedTelegramFailure"):
            self.assertNotIn("DO_NOT_LEAK_SESSION_SECRET", authorization_error_message(fake_error(name)))


if __name__ == "__main__":
    unittest.main()
