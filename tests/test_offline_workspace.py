"""The local workspace works without Telegram, Ollama or network access."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from offline_workspace import OfflineWorkspace


class OfflineWorkspaceTests(unittest.TestCase):
    def test_tasks_and_notes_persist_after_reopen(self):
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "private" / "workspace.db"
            with OfflineWorkspace(db_path) as store:
                task_id = store.add_task(" Купить молоко ")
                note_id = store.add_note(" Не забудь звонок ")
                self.assertEqual(store.list_tasks(), [(task_id, "Купить молоко", 0)])
                self.assertTrue(store.complete_task(task_id))
            with OfflineWorkspace(db_path) as store:
                self.assertEqual(store.list_tasks(), [(task_id, "Купить молоко", 1)])
                self.assertEqual(store.list_notes(), [(note_id, "Не забудь звонок")])
                self.assertFalse(store.complete_task(task_id))
                self.assertTrue(store.delete_task(task_id))
                self.assertTrue(store.delete_note(note_id))

    def test_limits_and_sql_injection_are_handled(self):
        with TemporaryDirectory() as directory:
            with OfflineWorkspace(Path(directory) / "workspace.db") as store:
                with self.assertRaises(ValueError):
                    store.add_task("  ")
                with self.assertRaises(ValueError):
                    store.add_note("A" * 1001)
                text = "'); DROP TABLE notes; --"
                store.add_task(text)
                self.assertEqual(store.list_tasks()[0][1], text)
                self.assertEqual(store.list_notes(), [])


if __name__ == "__main__":
    unittest.main()
