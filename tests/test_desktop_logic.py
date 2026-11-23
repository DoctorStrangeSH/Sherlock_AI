import unittest

from desktop_logic import ConversationSession, MAX_CONTEXT, context_window, conversation_title


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

    def test_conversation_title_uses_first_nonempty_user_message(self):
        messages = [
            {"role": "assistant", "content": "Привет"},
            {"role": "user", "content": "  Первый вопрос  "},
            {"role": "user", "content": "Второй вопрос"},
        ]
        self.assertEqual(conversation_title(messages), "Первый вопрос")

    def test_conversation_title_fallback_and_limit(self):
        self.assertEqual(conversation_title([]), "Диалог")
        self.assertEqual(conversation_title([{"role": "user", "content": "x" * 100}]), "x" * 70)

    def test_context_window_copies_latest_messages(self):
        messages = [{"role": "user", "content": str(index)} for index in range(20)]
        result = context_window(messages)
        self.assertEqual(len(result), MAX_CONTEXT)
        self.assertEqual(result[0]["content"], "8")
        result[0]["content"] = "changed"
        self.assertEqual(messages[-MAX_CONTEXT]["content"], "8")

    def test_context_window_nonpositive_limit(self):
        self.assertEqual(context_window([{"role": "user", "content": "x"}], 0), [])

    def test_clear(self):
        session = ConversationSession()
        session.record("тест", "ответ")
        session.clear()
        self.assertEqual(session.history, [])


if __name__ == "__main__":
    unittest.main()
