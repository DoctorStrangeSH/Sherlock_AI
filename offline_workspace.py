"""Local tasks and notes for the desktop assistant; no Telegram dependencies."""

import os
import json
from pathlib import Path
import sqlite3
from datetime import date


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
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL CHECK(duration_seconds > 0),
                session_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS saved_plans (
                id INTEGER PRIMARY KEY,
                plan_date TEXT NOT NULL,
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
        # Compatible migration: never recreate the existing tasks table.
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(tasks)")}
        with self.conn:
            if "priority" not in columns:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
            if "due_date" not in columns:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
            if "estimated_minutes" not in columns:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER")

    @staticmethod
    def _clean(value, maximum):
        text = " ".join(str(value).split())
        if not text or len(text) > maximum:
            raise ValueError(f"Текст должен содержать от 1 до {maximum} символов")
        return text

    @staticmethod
    def _validate_task_meta(priority="normal", due_date=None):
        if priority not in ("low", "normal", "high"):
            raise ValueError("Неизвестный приоритет задачи.")
        if due_date in ("", None):
            return priority, None
        if not isinstance(due_date, str) or len(due_date) != 10:
            raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД.")
        try:
            parsed = date.fromisoformat(due_date)
        except ValueError as exc:
            raise ValueError("Некорректная дата задачи.") from exc
        if parsed.isoformat() != due_date:
            raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД.")
        return priority, due_date

    def add_task(self, title, priority="normal", due_date=None):
        title = self._clean(title, 300)
        priority, due_date = self._validate_task_meta(priority, due_date)
        with self.conn:
            return self.conn.execute(
                "INSERT INTO tasks (title, priority, due_date) VALUES (?, ?, ?)",
                (title, priority, due_date)).lastrowid

    def list_tasks(self):
        return self.conn.execute("SELECT id, title, done FROM tasks ORDER BY done, id DESC").fetchall()

    def list_task_details(self):
        return self.conn.execute(
            "SELECT id, title, done, priority, due_date FROM tasks ORDER BY done, id DESC"
        ).fetchall()

    def list_task_estimates(self):
        """Task tuple: id, title, done, priority, due_date, estimated_minutes."""
        return self.conn.execute(
            "SELECT id, title, done, priority, due_date, estimated_minutes "
            "FROM tasks ORDER BY done, id DESC"
        ).fetchall()

    def update_task_estimate(self, task_id, minutes=None):
        """An unknown duration stays NULL; never silently invent an estimate."""
        if minutes is not None and (
            isinstance(minutes, bool) or not isinstance(minutes, int) or not 5 <= minutes <= 1440
        ):
            raise ValueError("Длительность должна быть от 5 до 1440 минут.")
        with self.conn:
            return self.conn.execute(
                "UPDATE tasks SET estimated_minutes = ? WHERE id = ?", (minutes, task_id)
            ).rowcount > 0

    def update_task_details(self, task_id, priority="normal", due_date=None):
        priority, due_date = self._validate_task_meta(priority, due_date)
        with self.conn:
            return self.conn.execute(
                "UPDATE tasks SET priority = ?, due_date = ? WHERE id = ?",
                (priority, due_date, task_id)).rowcount > 0

    def save_focus_session(self, task_id, title, duration_seconds, session_date):
        """Persist a completed session only after an explicit user choice."""
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise ValueError("Некорректный номер задачи.")
        title = self._clean(title, 300)
        if (not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool)
                or not 1 <= duration_seconds <= 86400):
            raise ValueError("Некорректная длительность фокус-сессии.")
        self._validate_task_meta("normal", session_date)
        with self.conn:
            return self.conn.execute(
                "INSERT INTO focus_sessions (task_id, title, duration_seconds, session_date) "
                "VALUES (?, ?, ?, ?)",
                (task_id, title, duration_seconds, session_date),
            ).lastrowid

    def focus_day_summary(self, session_date):
        """(session_count, total_seconds) for one local calendar day."""
        self._validate_task_meta("normal", session_date)
        return self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_seconds), 0) "
            "FROM focus_sessions WHERE session_date = ?",
            (session_date,),
        ).fetchone()

    def recent_focus_sessions(self, limit=5):
        """Recent saved focus sessions, newest first."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("Некорректное количество сессий.")
        return self.conn.execute(
            "SELECT task_id, title, duration_seconds, session_date "
            "FROM focus_sessions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def focus_week_summary(self, ending_day):
        """Count and total working seconds over seven calendar days."""
        from datetime import timedelta
        self._validate_task_meta("normal", ending_day)
        first_day = (date.fromisoformat(ending_day) - timedelta(days=6)).isoformat()
        return self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_seconds), 0) "
            "FROM focus_sessions WHERE session_date BETWEEN ? AND ?",
            (first_day, ending_day),
        ).fetchone()

    def nonurgent_tasks_due(self, day):
        """Only open, non-high-priority tasks due exactly on the selected day."""
        self._validate_task_meta("normal", day)
        return self.conn.execute(
            "SELECT id, title FROM tasks "
            "WHERE done = 0 AND due_date = ? AND priority IN ('low', 'normal') "
            "ORDER BY id",
            (day,),
        ).fetchall()

    def defer_nonurgent_tasks(self, day, task_ids):
        """Atomically move an explicitly approved snapshot of due-today tasks."""
        from datetime import timedelta
        self._validate_task_meta("normal", day)
        if not isinstance(task_ids, (list, tuple)) or not task_ids or len(task_ids) > 500:
            raise ValueError("Нет задач для переноса.")
        if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in task_ids):
            raise ValueError("Некорректный номер задачи.")
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("Номера задач повторяются.")
        next_day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        with self.conn:
            placeholders = ",".join("?" for _ in task_ids)
            existing = self.conn.execute(
                f"SELECT id FROM tasks WHERE id IN ({placeholders}) "
                "AND done = 0 AND due_date = ? AND priority IN ('low', 'normal')",
                (*task_ids, day),
            ).fetchall()
            if {row[0] for row in existing} != set(task_ids):
                raise ValueError("Список задач изменился. Повтори команду.")
            changed = self.conn.execute(
                f"UPDATE tasks SET due_date = ? WHERE id IN ({placeholders}) "
                "AND done = 0 AND due_date = ? AND priority IN ('low', 'normal')",
                (next_day, *task_ids, day),
            ).rowcount
            if changed != len(task_ids):
                raise ValueError("Не все задачи были перенесены.")
        return changed

    def save_plan(self, plan_date, content):
        """Save only an explicitly approved read-only plan snapshot."""
        if not isinstance(plan_date, str) or date.fromisoformat(plan_date).isoformat() != plan_date:
            raise ValueError("Некорректная дата плана.")
        if not isinstance(content, str) or not 1 <= len(content) <= 20000:
            raise ValueError("Некорректное содержимое плана.")
        with self.conn:
            return self.conn.execute(
                "INSERT INTO saved_plans (plan_date, content) VALUES (?, ?)",
                (plan_date, content)
            ).lastrowid

    def latest_plan(self):
        return self.conn.execute(
            "SELECT id, plan_date, content FROM saved_plans ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def list_saved_plans(self, limit=20):
        """Recent schedule metadata only; do not load full plan contents."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("Некорректное количество расписаний.")
        return self.conn.execute(
            "SELECT id, plan_date, created_at FROM saved_plans ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_saved_plan(self, plan_id):
        """Read an individual saved schedule without modifying it."""
        if not isinstance(plan_id, int) or isinstance(plan_id, bool) or plan_id <= 0:
            raise ValueError("Некорректный номер расписания.")
        return self.conn.execute(
            "SELECT id, plan_date, content FROM saved_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()

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
