"""Pure calendar classification of local tasks, based on the computer's local date."""
from datetime import date

PRIORITY_LABELS = {"low": "низкий", "normal": "обычный", "high": "высокий"}


def task_bucket(task, today=None):
    """Task tuple: (id, title, done, priority, due_date)."""
    today = today or date.today()
    if task[2]:
        return "done"
    deadline = task[4]
    if not deadline:
        return "unscheduled"
    if deadline < today.isoformat():
        return "overdue"
    if deadline == today.isoformat():
        return "today"
    return "upcoming"


def filtered_tasks(tasks, bucket, today=None):
    if bucket not in ("today", "overdue"):
        raise ValueError("Неизвестный фильтр задач.")
    return [task for task in tasks if task_bucket(task, today) == bucket]


def describe_task(task, today=None):
    state = task_bucket(task, today)
    markers = {"done": "✓", "overdue": "⚠ Просрочено", "today": "◉ Сегодня",
               "upcoming": "○", "unscheduled": "○"}
    suffix = (" · до " + task[4]) if task[4] else ""
    return "#{} {} {} · {}{}".format(task[0], markers[state], task[1],
                                     PRIORITY_LABELS.get(task[3], "обычный"), suffix)
