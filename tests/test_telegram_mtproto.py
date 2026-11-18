"""Offline tests for secure MTProto onboarding settings."""
import sys
import types
import unittest
from unittest.mock import patch

from telegram_network import telegram_client_options, parse_env_bool
from telegram_setup import delivery_hint


class TelegramNetworkTests(unittest.TestCase):
    def test_boolean_values(self):
        self.assertTrue(parse_env_bool("YES"))
        self.assertFalse(parse_env_bool("false"))
        with self.assertRaises(ValueError):
            parse_env_bool("sometimes")

    def test_direct_connection_unchanged(self):
        self.assertTrue(telegram_client_options({"TELEGRAM_USE_IPV6": "true"})["use_ipv6"])
        self.assertFalse(telegram_client_options({})["use_ipv6"])

    def test_mtproto_options(self):
        marker = object()
        randomized = object()
        connection = types.SimpleNamespace(ConnectionTcpMTProxyRandomizedIntermediate=randomized,
                                           ConnectionTcpMTProxyIntermediate=marker)
        with patch.dict(sys.modules, {"telethon": types.SimpleNamespace(connection=connection)}):
            options = telegram_client_options({
                "TELEGRAM_PROXY_TYPE": "mtproto",
                "TELEGRAM_PROXY_HOST": "proxy.example.org",
                "TELEGRAM_PROXY_PORT": "443",
                "TELEGRAM_PROXY_SECRET": "test-local-secret",
                "TELEGRAM_USE_IPV6": "true",
            })
        self.assertIs(options["connection"], marker)
        self.assertEqual(options["proxy"], ("proxy.example.org", 443, "test-local-secret"))
        self.assertFalse(options["use_ipv6"])

    def test_dd_secret_selects_randomized_intermediate(self):
        marker = object()
        connection = types.SimpleNamespace(ConnectionTcpMTProxyRandomizedIntermediate=marker,
                                           ConnectionTcpMTProxyIntermediate=object())
        with patch.dict(sys.modules, {"telethon": types.SimpleNamespace(connection=connection)}):
            options = telegram_client_options({"TELEGRAM_PROXY_TYPE": "mtproto",
                                               "TELEGRAM_PROXY_HOST": "proxy.example.org",
                                               "TELEGRAM_PROXY_PORT": "443",
                                               "TELEGRAM_PROXY_SECRET": "dd" + "00" * 16})
        self.assertIs(options["connection"], marker)

    def test_reject_bad_proxy_settings_without_revealing_secret(self):
        for change in ({"TELEGRAM_PROXY_PORT": "0"}, {"TELEGRAM_PROXY_PORT": "abc"},
                       {"TELEGRAM_PROXY_SECRET": ""}, {"TELEGRAM_PROXY_HOST": ""}):
            values = {"TELEGRAM_PROXY_TYPE": "mtproto", "TELEGRAM_PROXY_HOST": "example.org",
                      "TELEGRAM_PROXY_PORT": "443", "TELEGRAM_PROXY_SECRET": "never-print-this"}
            values.update(change)
            with self.assertRaises(ValueError) as caught:
                telegram_client_options(values)
            self.assertNotIn("never-print-this", str(caught.exception))

    def test_delivery_hints_do_not_include_server_payload(self):
        sent = types.SimpleNamespace(type=type("SentCodeTypeApp", (), {"phone_code_hash": "SENSITIVE"})())
        self.assertIn("служебный чат", delivery_hint(sent))
        self.assertNotIn("SENSITIVE", delivery_hint(sent))


if __name__ == "__main__":
    unittest.main()
