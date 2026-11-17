"""Backward-compatible task metadata migration and validation."""
import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
import unittest

from offline_workspace import OfflineWorkspace


class TaskMetadataTests(unittest.TestCase):
    def test_existing_database_keeps_tasks(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.sqlite"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)")
                db.execute("INSERT INTO tasks (title) VALUES ('Старая задача')")
            with OfflineWorkspace(path) as workspace:
                tasks = workspace.list_task_details()
                self.assertEqual(tasks[0][1], "Старая задача")
                self.assertEqual(tasks[0][3:], ("normal", None))
                self.assertTrue(workspace.update_task_details(tasks[0][0], "high", "2026-12-31"))
                self.assertEqual(workspace.list_task_details()[0][3:], ("high", "2026-12-31"))
            with OfflineWorkspace(path) as workspace:
                self.assertEqual(workspace.list_task_details()[0][3:], ("high", "2026-12-31"))

    def test_metadata_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            with OfflineWorkspace(Path(temp) / "tasks.sqlite") as workspace:
                with self.assertRaises(ValueError):
                    workspace.add_task("Неверно", priority="urgent")
                with self.assertRaises(ValueError):
                    workspace.add_task("Неверно", due_date="2026-02-30")
                task_id = workspace.add_task("Новая", priority="low", due_date="2026-12-01")
                self.assertEqual(workspace.list_task_details()[0], (task_id, "Новая", 0, "low", "2026-12-01"))


if __name__ == "__main__":
    unittest.main()
