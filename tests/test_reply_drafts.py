import unittest

from reply_drafts import can_prepare_draft, draft_question, display_draft


class DraftSafetyTests(unittest.TestCase):
    def test_only_opted_in_private_allowlisted_incoming(self):
        args = dict(enabled=True, private=True, outgoing=False, sender_id=12,
                    owner_id=1, allowed_ids={12}, text="Привет")
        self.assertTrue(can_prepare_draft(**args))
        for name, value in [("enabled", False), ("private", False),
                            ("outgoing", True), ("sender_id", 1),
                            ("allowed_ids", set()), ("text", "")]:
            modified = dict(args, **{name: value})
            self.assertFalse(can_prepare_draft(**modified))

    def test_rejects_long_messages(self):
        self.assertFalse(can_prepare_draft(
            enabled=True, private=True, outgoing=False, sender_id=12,
            owner_id=1, allowed_ids={12}, text="x" * 1801
        ))

    def test_draft_has_no_send_instruction(self):
        prompt = draft_question("Оплати сегодня", "Анна")
        self.assertIn("ЧЕРНОВИК", prompt)
        shown = display_draft("Анна", "Хорошо, уточню.")
        self.assertIn("НЕ ОТПРАВЛЕНО", shown)


if __name__ == "__main__":
    unittest.main()
