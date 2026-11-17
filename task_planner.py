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



def build_day_parts(tasks, today=None, capacity=9):
    """Suggest morning/day/evening groups; no task durations or start times assumed."""
    today = today or date.today()
    today_iso = today.isoformat()
    relevant = [
        task for task in tasks
        if not task[2] and (
            (task[4] is not None and task[4] <= today_iso)
            or (not task[4] and task[3] == "high")
        )
    ]
    priority = {"high": 0, "normal": 1, "low": 2}
    relevant.sort(key=lambda task: (
        0 if task_bucket(task, today) == "overdue" else
        1 if task[4] == today_iso else 2,
        priority.get(task[3], 1), task[4] or "9999-12-31", task[0],
    ))
    lines = ["🕘 Предложение на " + today.strftime("%d.%m.%Y")]
    if not relevant:
        return "\n".join(lines + ["На сегодня нет срочных задач."])
    groups = (("🌅 Утро", relevant[:3]), ("☀ День", relevant[3:6]),
              ("🌙 Вечер", relevant[6:max(6, min(capacity, 9))]))
    for heading, items in groups:
        lines.append(heading)
        lines.extend("• " + describe_task(task, today) for task in items)
        if not items:
            lines.append("• Свободное время")
    if len(relevant) > max(6, min(capacity, 9)):
        lines.append("⚠ Дополнительно осталось {} задач(и). День может быть перегружен.".format(
            len(relevant) - max(6, min(capacity, 9))))
    lines.append("Это ориентировочные блоки, не назначенные часы. Сроки задач не изменены.")
    return "\n".join(lines)



def build_time_budget_plan(tasks, budget_minutes, today=None):
    """Suggest tasks that fit, using ONLY explicit duration estimates."""
    if isinstance(budget_minutes, bool) or not isinstance(budget_minutes, int) or not 15 <= budget_minutes <= 1440:
        raise ValueError("Бюджет должен быть от 15 минут до 24 часов.")
    today = today or date.today()
    today_iso = today.isoformat()
    candidates = [task for task in tasks if not task[2] and
                  ((task[4] and task[4] <= today_iso) or
                   (not task[4] and task[3] == "high"))]
    priority = {"high": 0, "normal": 1, "low": 2}
    candidates.sort(key=lambda task: (
        0 if task[4] and task[4] < today_iso else 1 if task[4] else 2,
        priority.get(task[3], 1), task[4] or "9999-12-31", task[0],
    ))
    remaining = budget_minutes
    chosen, deferred, unknown = [], [], []
    for task in candidates:
        estimate = task[5]
        if estimate is None:
            unknown.append(task)
        elif estimate <= remaining:
            chosen.append(task)
            remaining -= estimate
        else:
            deferred.append(task)
    lines = ["⏳ План на {} мин. · {}".format(budget_minutes, today.strftime("%d.%m.%Y"))]
    if chosen:
        lines.append("Вмещается в доступное время:")
        lines.extend("• {} · ~{} мин.".format(describe_task(task, today), task[5]) for task in chosen)
    else:
        lines.append("Пока нет задач с известной длительностью, которые помещаются в бюджет.")
    lines.append("Запланировано: {} мин. · Остаток: {} мин.".format(budget_minutes - remaining, remaining))
    if deferred:
        lines.append("Не помещаются: " + ", ".join("#{}".format(task[0]) for task in deferred[:12]))
    if unknown:
        lines.append("Длительность не указана: " + ", ".join("#{}".format(task[0]) for task in unknown[:12]))
        lines.append("Укажи оценку: «Установи длительность задачи #5: 45 минут».")
    lines.append("Это рекомендация. Расписание и сроки задач не изменены.")
    return "\n".join(lines)
