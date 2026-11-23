"""Permission revocation must discard only the affected contact's private state."""
import unittest

from conversation_context import RecentChatContext
from draft_queue import DraftQueue


class ContactRevocationTests(unittest.TestCase):
    def test_revoke_removes_target_drafts_only(self):
        queue = DraftQueue()
        first = queue.add(101, "A", "Hello A")
        second = queue.add(202, "B", "Hello B")
        self.assertEqual(queue.cancel_for_contact(101), 1)
        self.assertIsNone(queue.peek(first.draft_id))
        self.assertIsNotNone(queue.peek(second.draft_id))
        self.assertEqual(queue.cancel_for_contact(101), 0)

    def test_revoke_forgets_only_target_context(self):
        context = RecentChatContext()
        context.add(101, "contact", "Hello A")
        context.add(202, "contact", "Hello B")
        context.forget(101)
        self.assertEqual(context.recent(101), [])
        self.assertEqual(context.recent(202), [("contact", "Hello B")])


if __name__ == "__main__":
    unittest.main()
