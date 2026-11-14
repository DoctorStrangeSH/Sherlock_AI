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
