"""Non-intrusive, in-app task reminders with per-day deduplication."""
from datetime import date, timedelta

from task_overview import describe_task


class ReminderTracker:
    """Keeps reminders once per task, day and deadline in a running session."""

    def __init__(self):
        self.seen = set()

    def due_messages(self, tasks, today=None, limit=3):
        today = today or date.today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        ready = []
        for task in tasks:
            task_id, _, done, _, deadline = task
            if done or not deadline or deadline > tomorrow:
                continue
            key = (task_id, today.isoformat(), deadline)
            if key in self.seen:
                continue
            ready.append((task, key))
        ready.sort(key=lambda item: (item[0][4], item[0][0]))
        # Mark only messages that are actually delivered, not suppressed by the limit.
        displayed = ready[:max(0, limit)]
        for _, key in displayed:
            self.seen.add(key)
        if not displayed:
            return ""
        lines = ["⏰ Напоминания о задачах:"]
        for task, _ in displayed:
            suffix = " · срок завтра" if task[4] == tomorrow else ""
            lines.append(describe_task(task, today) + suffix)
        if len(ready) > len(displayed):
            lines.append("Ещё задач к напоминанию: {}.".format(len(ready) - len(displayed)))
        return "\n".join(lines)
