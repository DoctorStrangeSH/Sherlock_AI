import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from filters import SmartFilter
from security import Security


class FakeDB:
    pass


class CoreTests(unittest.TestCase):
    def test_filter_categories(self):
        filt = SmartFilter()
        self.assertEqual(filt.get_message_category(1, "Это срочно"), "important")
        self.assertEqual(filt.get_message_category(1, "Привет"), "normal")
        self.assertEqual(filt.get_message_category(1, "РЕКЛАМА"), "spam")

    def test_rate_limit(self):
        guard = Security(FakeDB())
        for _ in range(10):
            self.assertTrue(guard.check_rate_limit(7))
        self.assertFalse(guard.check_rate_limit(7))
        self.assertTrue(guard.check_rate_limit(8))

    def test_ban(self):
        guard = Security(FakeDB())
        guard.ban_user(5)
        self.assertTrue(guard.is_banned(5))
        guard.unban_user(5)
        self.assertFalse(guard.is_banned(5))


if __name__ == "__main__":
    unittest.main()
