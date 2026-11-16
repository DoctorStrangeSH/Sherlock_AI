"""Local tasks and notes for the desktop assistant; no Telegram dependencies."""

import os
import json
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
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                messages TEXT NOT NULL,
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

    def update_note(self, note_id, content):
        content = self._clean(content, 1000)
        with self.conn:
            return self.conn.execute("UPDATE notes SET content = ? WHERE id = ?",
                                     (content, note_id)).rowcount > 0

    def list_notes(self):
        return self.conn.execute("SELECT id, content FROM notes ORDER BY id DESC").fetchall()

    def delete_note(self, note_id):
        with self.conn:
            return self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0

    def add_memory(self, content):
        content = self._clean(content, 500)
        with self.conn:
            return self.conn.execute("INSERT INTO memories (content) VALUES (?)", (content,)).lastrowid

    def list_memories(self):
        return self.conn.execute("SELECT id, content FROM memories ORDER BY id DESC").fetchall()

    def update_memory(self, memory_id, content):
        content = self._clean(content, 500)
        with self.conn:
            return self.conn.execute("UPDATE memories SET content = ? WHERE id = ?",
                                     (content, memory_id)).rowcount > 0

    def delete_memory(self, memory_id):
        with self.conn:
            return self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,)).rowcount > 0

    def save_conversation(self, title, messages):
        title = self._clean(title, 100)
        if not isinstance(messages, list) or not messages or len(messages) > 200:
            raise ValueError("Диалог должен содержать от 1 до 200 сообщений")
        safe = []
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
                raise ValueError("Недопустимый формат диалога")
            content = message.get("content")
            if not isinstance(content, str) or len(content) > 4000:
                raise ValueError("Недопустимое сообщение")
            safe.append({"role": message["role"], "content": content})
        serialized = json.dumps(safe, ensure_ascii=False)
        with self.conn:
            return self.conn.execute(
                "INSERT INTO conversations (title, messages) VALUES (?, ?)",
                (title, serialized)).lastrowid

    def list_conversations(self):
        return self.conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY id DESC").fetchall()

    def load_conversation(self, conversation_id):
        row = self.conn.execute(
            "SELECT messages FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete_conversation(self, conversation_id):
        with self.conn:
            return self.conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)).rowcount > 0

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
