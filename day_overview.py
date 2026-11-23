"""Read-only summary for the desktop 'Мой день' page."""
from datetime import datetime
import re

from task_scheduler import describe_current_slot


def render_timeline(plan, at=None):
    """Mark finished, active and upcoming time blocks in a saved schedule."""
    at = at or datetime.now()
    current = at.hour * 60 + at.minute
    result = []
    for line in plan.splitlines():
        if line.startswith("🕘 "):
            result.append(line)
            continue
        if not line.startswith(("• ", "☕ ")):
            continue
        match = re.match(r"^[•☕] (\d{2}):(\d{2})–(\d{2}):(\d{2}) ", line)
        if not match:
            continue
        h1, m1, h2, m2 = map(int, match.groups())
        if h1 > 23 or h2 > 24 or m1 > 59 or m2 > 59 or (h2 == 24 and m2):
            continue
        start, end = h1 * 60 + m1, h2 * 60 + m2
        if start >= end:
            continue
        if current >= end:
            result.append("✓  " + line)
        elif current < start:
            result.append("○  " + line)
        else:
            result.append(f"▶  {line} · осталось {end - current} мин.")
    return "\n".join(result) if result else "Нет временных блоков."


def build_day_overview(tasks, saved_plan=None, now=None):
    """Return status, progress and schedule text without changing tasks."""
    now = now or datetime.now()
    day = now.date().isoformat()
    relevant = [task for task in tasks if task[4] and task[4] <= day]
    done = sum(1 for task in relevant if task[2])
    overdue = [task for task in relevant if not task[2] and task[4] < day]
    due = [task for task in relevant if not task[2] and task[4] == day]
    header = (f"Сегодня · {now:%d.%m.%Y}\n"
              f"Задачи со сроком до сегодня: {done}/{len(relevant)} выполнено · "
              f"На сегодня: {len(due)} · Просрочено: {len(overdue)}")
    upcoming = sorted(due + overdue, key=lambda task: (
        task[4], {"high": 0, "normal": 1, "low": 2}.get(task[3], 1), task[0]))
    lines = [f"#{task[0]} · {task[1]} · {task[4]}" for task in upcoming[:12]]
    task_text = "\n".join(lines) if lines else "Нет невыполненных задач со сроком на сегодня или раньше."
    if len(upcoming) > 12:
        task_text += f"\n…и ещё {len(upcoming) - 12}. Полный список доступен в разделе «Задачи»."

    if saved_plan and saved_plan[1] == day:
        plan = saved_plan[2]
        status = describe_current_slot(plan, day, at=now)
        timeline = render_timeline(plan, at=now)
    else:
        status = "Нет сохранённого расписания на сегодня."
        timeline = "Создай план через чат и сохрани его, чтобы увидеть здесь временную шкалу."
    return header, status, task_text, timeline
