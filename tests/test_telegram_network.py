"""Telegram network option tests; no live Telegram requests."""
import unittest

from telegram_network import parse_env_bool, telegram_client_options


class TelegramNetworkTests(unittest.TestCase):
    def test_boolean_values(self):
        self.assertTrue(parse_env_bool("true"))
        self.assertTrue(parse_env_bool("YES"))
        self.assertFalse(parse_env_bool("false"))
        self.assertFalse(parse_env_bool("0"))

    def test_default_preserves_legacy_ipv4_behavior(self):
        self.assertFalse(parse_env_bool(None, default=False))
        self.assertTrue(parse_env_bool(None, default=True))

    def test_rejects_invalid_boolean(self):
        with self.assertRaises(ValueError):
            parse_env_bool("sometimes")

    def test_options_enable_ipv6_when_configured(self):
        options = telegram_client_options({"TELEGRAM_USE_IPV6": "true"})
        self.assertTrue(options["use_ipv6"])
        self.assertEqual(options["timeout"], 20)
        self.assertEqual(options["connection_retries"], 3)

    def test_options_default_to_ipv4_for_existing_installations(self):
        self.assertFalse(telegram_client_options({})["use_ipv6"])


if __name__ == "__main__":
    unittest.main()
