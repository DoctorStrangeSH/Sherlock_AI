"""Tests for local-only transport probes; never contact Telegram."""
import asyncio
import sys
import types
import unittest
from unittest.mock import patch

from telegram_connection_probe import probe


class FakeClient:
    instances = []

    def __init__(self, session, api_id, api_hash, **options):
        self.options = options
        self.connected = False
        self.disconnected = False
        self.instances.append(self)

    async def connect(self):
        self.connected = True

    def is_connected(self):
        return self.connected

    async def disconnect(self):
        self.disconnected = True


class ProbeTests(unittest.TestCase):
    def test_probe_connects_and_discards_temporary_session(self):
        fake_telethon = types.SimpleNamespace(TelegramClient=FakeClient)
        fake_sessions = types.SimpleNamespace(MemorySession=object)
        with patch.dict(sys.modules, {"telethon": fake_telethon, "telethon.sessions": fake_sessions}):
            self.assertTrue(asyncio.run(probe({"use_ipv6": True})))
        self.assertTrue(FakeClient.instances[-1].disconnected)

    def test_probe_disconnects_after_transport_exception(self):
        class FailedClient(FakeClient):
            async def connect(self):
                raise OSError("connect failed")

        fake_telethon = types.SimpleNamespace(TelegramClient=FailedClient)
        fake_sessions = types.SimpleNamespace(MemorySession=object)
        with patch.dict(sys.modules, {"telethon": fake_telethon, "telethon.sessions": fake_sessions}):
            with self.assertRaises(OSError):
                asyncio.run(probe({"use_ipv6": False}))
        self.assertTrue(FailedClient.instances[-1].disconnected)


if __name__ == "__main__":
    unittest.main()
