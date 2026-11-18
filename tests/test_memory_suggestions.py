"""User approval gate for proposed chat memories."""
import unittest

from memory_suggestions import proposed_memory


class MemorySuggestionTests(unittest.TestCase):
    def test_extracts_only_explicit_requests(self):
        self.assertEqual(proposed_memory("Запомни, что люблю фиолетовый."), "люблю фиолетовый")
        self.assertEqual(proposed_memory("запомни мой любимый цвет — синий"), "мой любимый цвет — синий")
        self.assertIsNone(proposed_memory("Мне нравится синий"))
        self.assertIsNone(proposed_memory("Запомни, что "))

    def test_rejects_sensitive_and_oversized(self):
        self.assertIsNone(proposed_memory("Запомни мой пароль 1234"))
        self.assertIsNone(proposed_memory("Запомни API hash abc"))
        self.assertIsNone(proposed_memory("Запомни " + "я" * 501))


if __name__ == "__main__":
    unittest.main()
