import unittest

from draft_queue import DraftQueue, MAX_DRAFTS, TTL_SECONDS


class DraftQueueTests(unittest.TestCase):
    def test_explicit_confirmation_consumes_only_once(self):
        drafts = DraftQueue()
        draft = drafts.add(22, "Анна", "Привет!")
        self.assertIsNone(drafts.take_for_send(draft.draft_id, enabled=False, allowed_ids={22}))
        self.assertIsNone(drafts.take_for_send(draft.draft_id, enabled=True, allowed_ids=set()))
        self.assertEqual(drafts.take_for_send(draft.draft_id, enabled=True, allowed_ids={22}), draft)
        self.assertIsNone(drafts.take_for_send(draft.draft_id, enabled=True, allowed_ids={22}))

    def test_expiry(self):
        clock = [0.0]
        drafts = DraftQueue(clock=lambda: clock[0])
        draft = drafts.add(22, "Анна", "Привет!")
        clock[0] = TTL_SECONDS
        self.assertIsNone(drafts.peek(draft.draft_id))

    def test_cancel(self):
        drafts = DraftQueue()
        draft = drafts.add(22, "Анна", "Привет!")
        self.assertTrue(drafts.cancel(draft.draft_id))
        self.assertFalse(drafts.cancel(draft.draft_id))

    def test_max_drafts_discards_oldest(self):
        drafts = DraftQueue()
        first = drafts.add(22, "Анна", "1")
        for _ in range(MAX_DRAFTS):
            drafts.add(22, "Анна", "ещё")
        self.assertIsNone(drafts.peek(first.draft_id))

    def test_edit_keeps_target_and_expiry(self):
        clock = [0.0]
        drafts = DraftQueue(clock=lambda: clock[0])
        original = drafts.add(22, "Анна", "старое")
        clock[0] = 100.0
        edited = drafts.edit(original.draft_id, "новое", enabled=True, allowed_ids={22})
        self.assertEqual(edited.reply, "новое")
        self.assertEqual(edited.recipient_id, original.recipient_id)
        self.assertEqual(edited.created_at, original.created_at)
        sent = drafts.take_for_send(original.draft_id, enabled=True, allowed_ids={22})
        self.assertEqual(sent.reply, "новое")

    def test_edit_requires_allowed_active_contact_and_valid_text(self):
        drafts = DraftQueue()
        item = drafts.add(22, "Анна", "старое")
        self.assertIsNone(drafts.edit(item.draft_id, "a", enabled=False, allowed_ids={22}))
        self.assertIsNone(drafts.edit(item.draft_id, "a", enabled=True, allowed_ids=set()))
        with self.assertRaises(ValueError):
            drafts.edit(item.draft_id, "", enabled=True, allowed_ids={22})
        with self.assertRaises(ValueError):
            drafts.edit(item.draft_id, "a" * 2501, enabled=True, allowed_ids={22})
        self.assertEqual(drafts.peek(item.draft_id).reply, "старое")

    def test_invalid_payloads(self):
        drafts = DraftQueue()
        with self.assertRaises(ValueError):
            drafts.add(0, "x", "hello")
        with self.assertRaises(ValueError):
            drafts.add(2, "x", "")
        with self.assertRaises(ValueError):
            drafts.add(2, "x", "a" * 2501)


if __name__ == "__main__":
    unittest.main()
