"""Editing notes preserves IDs and keeps all data local."""
import tempfile
from pathlib import Path
import unittest

from offline_workspace import OfflineWorkspace


class NoteEditTests(unittest.TestCase):
    def test_edit_and_persist_note(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.sqlite3"
            with OfflineWorkspace(path) as workspace:
                note_id = workspace.add_note("Первый текст")
                self.assertTrue(workspace.update_note(note_id, "Обновлённый текст"))
                self.assertEqual(workspace.list_notes(), [(note_id, "Обновлённый текст")])
                self.assertFalse(workspace.update_note(999999, "Нет такой записи"))
                with self.assertRaises(ValueError):
                    workspace.update_note(note_id, "")
            with OfflineWorkspace(path) as workspace:
                self.assertEqual(workspace.list_notes(), [(note_id, "Обновлённый текст")])


if __name__ == "__main__":
    unittest.main()
