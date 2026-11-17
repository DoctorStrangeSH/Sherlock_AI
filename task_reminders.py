"""Non-intrusive, in-app task reminders with persistent per-day deduplication."""
from datetime import date, timedelta
import json
from pathlib import Path

from task_overview import describe_task


def valid_reminder_time(value):
    """Accept only an exact 24-hour HH:MM time."""
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return False
    h, m = value[:2], value[3:]
    return h.isascii() and m.isascii() and h.isdigit() and m.isdigit() and int(h) < 24 and int(m) < 60


class ReminderTracker:
    """Shows a task at most once per day, including across app restarts."""

    def __init__(self, state_path=None):
        self.state_path = Path(state_path) if state_path else None
        self.seen = set()
        if self.state_path:
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.seen = {item for item in data[:500] if isinstance(item, str) and len(item) < 100}
            except (OSError, ValueError, TypeError):
                pass

    def _save(self):
        if self.state_path is None:
            return
        # Keep only the last seven days; old reminders can never be relevant again.
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        self.seen = {key for key in self.seen if len(key.split("|")) == 3 and key.split("|")[1] >= cutoff}
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(sorted(self.seen)[-500:], ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.state_path)
        except OSError:
            pass  # Disk errors must not interrupt the desktop application.

    def due_messages(self, tasks, today=None, limit=3):
        today = today or date.today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        ready = []
        for task in tasks:
            task_id, _, done, _, deadline = task
            if done or not deadline or deadline > tomorrow:
                continue
            key = "{}|{}|{}".format(task_id, today.isoformat(), deadline)
            if key in self.seen:
                continue
            ready.append((task, key))
        ready.sort(key=lambda item: (item[0][4], item[0][0]))
        displayed = ready[:max(0, limit)]
        for _, key in displayed:
            self.seen.add(key)
        if displayed:
            self._save()
        if not displayed:
            return ""
        lines = ["⏰ Напоминания о задачах:"]
        for task, _ in displayed:
            suffix = " · срок завтра" if task[4] == tomorrow else ""
            lines.append(describe_task(task, today) + suffix)
        if len(ready) > len(displayed):
            lines.append("Ещё задач к напоминанию: {}.".format(len(ready) - len(displayed)))
        return "\n".join(lines)
