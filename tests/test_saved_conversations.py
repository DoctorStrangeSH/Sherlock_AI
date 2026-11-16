"""Saved chat sessions are opt-in and separate from memory."""
import tempfile
from pathlib import Path
import unittest

from offline_workspace import OfflineWorkspace


class SavedConversationTests(unittest.TestCase):
    def test_save_restore_delete(self):
        messages = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте!"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.sqlite3"
            with OfflineWorkspace(path) as store:
                self.assertEqual(store.list_conversations(), [])
                conversation_id = store.save_conversation("Первый диалог", messages)
                self.assertEqual(store.load_conversation(conversation_id), messages)
                self.assertEqual(store.list_memories(), [])
                with self.assertRaises(ValueError):
                    store.save_conversation("Нельзя", [{"role": "system", "content": "hidden"}])
            with OfflineWorkspace(path) as store:
                self.assertEqual(store.load_conversation(conversation_id), messages)
                self.assertTrue(store.delete_conversation(conversation_id))
                self.assertIsNone(store.load_conversation(conversation_id))


if __name__ == "__main__":
    unittest.main()
