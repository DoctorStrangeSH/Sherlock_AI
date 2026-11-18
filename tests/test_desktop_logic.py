import unittest

from desktop_logic import ConversationSession, MAX_CONTEXT


class DesktopLogicTests(unittest.TestCase):
    def test_successful_turn_is_saved(self):
        session = ConversationSession()
        self.assertTrue(session.record("Привет", "Привет!"))
        self.assertEqual(session.snapshot(), [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Привет!"},
        ])

    def test_failed_turn_is_not_saved(self):
        session = ConversationSession()
        self.assertFalse(session.record("Привет", "Локальная модель недоступна."))
        self.assertEqual(session.history, [])

    def test_context_is_bounded(self):
        session = ConversationSession()
        for number in range(20):
            session.record(str(number), "ответ")
        self.assertEqual(len(session.history), MAX_CONTEXT)
        self.assertEqual(session.history[0]["content"], "14")

    def test_snapshot_cannot_mutate_internal_history(self):
        session = ConversationSession()
        session.record("тест", "ответ")
        snapshot = session.snapshot()
        snapshot[0]["content"] = "заменено"
        self.assertEqual(session.history[0]["content"], "тест")

    def test_clear(self):
        session = ConversationSession()
        session.record("тест", "ответ")
        session.clear()
        self.assertEqual(session.history, [])


if __name__ == "__main__":
    unittest.main()
