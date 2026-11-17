"""Read-only deterministic day/week plans from locally stored tasks."""
from datetime import date, timedelta

from task_overview import describe_task, task_bucket


def build_task_plan(tasks, period="today", today=None, limit=12):
    """Format a prioritized recommendation without editing tasks or calling a model."""
    if period not in ("today", "week"):
        raise ValueError("Неизвестный период планирования.")
    today = today or date.today()
    last_day = today if period == "today" else today + timedelta(days=6)
    today_iso, last_iso = today.isoformat(), last_day.isoformat()
    open_tasks = [task for task in tasks if not task[2]]
    due = [task for task in open_tasks if task[4] and task[4] <= last_iso]
    # Undated high-priority tasks are useful to review, but not a hard deadline.
    undated_high = [task for task in open_tasks if not task[4] and task[3] == "high"]
    candidates = due + undated_high
    priority_order = {"high": 0, "normal": 1, "low": 2}
    candidates.sort(key=lambda task: (
        0 if task_bucket(task, today) == "overdue" else 1 if task[4] == today_iso
        else 2 if task[4] else 3,
        task[4] or "9999-12-31",
        priority_order.get(task[3], 1),
        task[0],
    ))
    title = "📅 План на сегодня" if period == "today" else "🗓 План на 7 дней"
    lines = [title + " · " + today.strftime("%d.%m.%Y")]
    overdue_count = sum(1 for task in due if task[4] < today_iso)
    lines.append("Просрочено: {} · В плане: {} · Без срока (важные): {}".format(
        overdue_count, len(due), len(undated_high)))
    if not candidates:
        lines.append("Срочных задач нет. Можно запланировать новую задачу или отдохнуть.")
        return "\n".join(lines)
    for index, task in enumerate(candidates[:max(0, limit)], 1):
        lines.append("{}. {}".format(index, describe_task(task, today)))
    remaining = len(candidates) - max(0, limit)
    if remaining > 0:
        lines.append("…ещё {} задач(и) в разделе «Задачи».".format(remaining))
    lines.append("Порядок рекомендательный: просроченные и ближайшие сроки — первыми.")
    return "\n".join(lines)
