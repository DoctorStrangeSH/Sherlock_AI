"""Local tasks and notes for the desktop assistant; no Telegram dependencies."""

import os
from pathlib import Path
import sqlite3


def default_database_path():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "SherlockAI" / "workspace.sqlite3"
    return Path.home() / ".local" / "share" / "SherlockAI" / "workspace.sqlite3"


class OfflineWorkspace:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

    @staticmethod
    def _clean(value, maximum):
        text = " ".join(str(value).split())
        if not text or len(text) > maximum:
            raise ValueError(f"Текст должен содержать от 1 до {maximum} символов")
        return text

    def add_task(self, title):
        title = self._clean(title, 300)
        with self.conn:
            return self.conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,)).lastrowid

    def list_tasks(self):
        return self.conn.execute("SELECT id, title, done FROM tasks ORDER BY done, id DESC").fetchall()

    def complete_task(self, task_id):
        with self.conn:
            return self.conn.execute("UPDATE tasks SET done = 1 WHERE id = ? AND done = 0", (task_id,)).rowcount > 0

    def delete_task(self, task_id):
        with self.conn:
            return self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount > 0

    def add_note(self, content):
        content = self._clean(content, 1000)
        with self.conn:
            return self.conn.execute("INSERT INTO notes (content) VALUES (?)", (content,)).lastrowid

    def list_notes(self):
        return self.conn.execute("SELECT id, content FROM notes ORDER BY id DESC").fetchall()

    def delete_note(self, note_id):
        with self.conn:
            return self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
