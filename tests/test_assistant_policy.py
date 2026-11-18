import unittest
from types import SimpleNamespace

from assistant_access import is_saved_messages_owner
from personality import PERSONAS, build_system_prompt


class AssistantPolicyTests(unittest.TestCase):
    def test_private_saved_messages_only(self):
        event = SimpleNamespace(
            out=True, is_private=True, sender_id=42, chat_id=42
        )
        self.assertTrue(is_saved_messages_owner(event, 42))
        for change in (
            {"out": False},
            {"is_private": False},
            {"sender_id": 100},
            {"chat_id": 100},
        ):
            self.assertFalse(is_saved_messages_owner(
                SimpleNamespace(**{**vars(event), **change}), 42
            ))

    def test_persona_styles_are_bounded(self):
        for tone in PERSONAS:
            prompt = build_system_prompt(tone)
            self.assertIn("ИИ-ассистент", prompt)
            self.assertIn("Не выдавай секреты", prompt)
        self.assertEqual(
            build_system_prompt("unknown"),
            build_system_prompt("warm")
        )


if __name__ == "__main__":
    unittest.main()
