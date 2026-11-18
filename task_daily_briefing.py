"""A compact, read-only local task briefing shown when Sherlock AI starts."""

from datetime import date

from task_overview import describe_task, task_bucket


def build_daily_briefing(tasks, today=None, max_items=4):
    """Return a Russian briefing for due/overdue/high-priority open tasks.

    Tasks are (id, title, done, priority, due_date). This does not modify tasks.
    """
    today = today or date.today()
    active = [task for task in tasks if not task[2]]
    overdue = [task for task in active if task_bucket(task, today) == "overdue"]
    due_today = [task for task in active if task_bucket(task, today) == "today"]
    high = [task for task in active if task[3] == "high"]

    if not (overdue or due_today or high):
        return ""

    lines = [
        "📋 Сводка задач на " + today.strftime("%d.%m.%Y"),
        "На сегодня: {} · Просрочено: {} · Высокий приоритет: {}".format(
            len(due_today), len(overdue), len(high)
        ),
    ]

    # One task must not be displayed twice, even if it is both due and high-priority.
    ranked = sorted(active, key=lambda task: (
        {"overdue": 0, "today": 1}.get(task_bucket(task, today),
                                     2 if task[3] == "high" else 3),
        0 if task[3] == "high" else 1,
        task[4] or "9999-12-31",
        task[0],
    ))
    relevant = [task for task in ranked
                if task_bucket(task, today) in ("overdue", "today") or task[3] == "high"]
    if max_items > 0:
        lines.extend(describe_task(task, today) for task in relevant[:max_items])
        if len(relevant) > max_items:
            lines.append("…и ещё {} задач(и). Открой раздел «Задачи».".format(
                len(relevant) - max_items
            ))
    return "\n".join(lines)
