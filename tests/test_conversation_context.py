import unittest

from conversation_context import (
    RecentChatContext, MAX_CONTACTS, MAX_MESSAGES, MAX_TEXT_LENGTH
)


class RecentChatContextTests(unittest.TestCase):
    def test_context_is_isolated_by_contact(self):
        context = RecentChatContext()
        context.add(21, "contact", "Привет")
        context.add(22, "owner", "Пока")
        self.assertEqual(context.recent(21), [("contact", "Привет")])
        self.assertEqual(context.recent(22), [("owner", "Пока")])

    def test_limits_and_command_filtering(self):
        context = RecentChatContext()
        for i in range(MAX_MESSAGES + 3):
            context.add(21, "contact", str(i))
        self.assertEqual(len(context.recent(21)), MAX_MESSAGES)
        context.add(21, "owner", ".senddraft 12")
        self.assertEqual(len(context.recent(21)), MAX_MESSAGES)
        context.add(21, "contact", "a" * 2000)
        self.assertEqual(len(context.recent(21)[-1][1]), MAX_TEXT_LENGTH)

    def test_eviction_and_clear(self):
        context = RecentChatContext()
        for i in range(MAX_CONTACTS + 1):
            context.add(i + 1, "contact", "test")
        self.assertEqual(context.recent(1), [])
        context.clear()
        self.assertEqual(context.recent(MAX_CONTACTS + 1), [])

    def test_invalid_data(self):
        context = RecentChatContext()
        context.add(-1, "contact", "hi")
        context.add(1, "assistant", "hi")
        context.add(1, "owner", "")
        self.assertEqual(context.recent(1), [])


if __name__ == "__main__":
    unittest.main()
