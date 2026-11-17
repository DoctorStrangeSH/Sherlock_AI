"""Pure local time-block scheduling using explicit task estimates only."""
from datetime import date

from task_overview import describe_task


def build_timed_schedule(tasks, start_time, available_minutes, break_minutes=10, today=None):
    """Return a read-only Russian schedule; no guessed durations or writes."""
    today = today or date.today()
    if not isinstance(start_time, str) or len(start_time) != 5 or start_time[2] != ":":
        raise ValueError("Время начала должно быть ЧЧ:ММ.")
    hours, minutes = start_time[:2], start_time[3:]
    if not (hours.isascii() and minutes.isascii() and hours.isdigit() and minutes.isdigit()):
        raise ValueError("Некорректное время начала.")
    hour, minute = int(hours), int(minutes)
    if hour >= 24 or minute >= 60:
        raise ValueError("Некорректное время начала.")
    if (isinstance(available_minutes, bool) or not isinstance(available_minutes, int)
            or not 15 <= available_minutes <= 1440):
        raise ValueError("Доступное время должно быть от 15 до 1440 минут.")
    if (isinstance(break_minutes, bool) or not isinstance(break_minutes, int)
            or not 0 <= break_minutes <= 60):
        raise ValueError("Перерыв должен быть от 0 до 60 минут.")
    start = hour * 60 + minute
    if start + available_minutes > 1440:
        raise ValueError("Расписание должно закончиться до полуночи.")
    end = start + available_minutes
    today_iso = today.isoformat()
    priority = {"high": 0, "normal": 1, "low": 2}
    candidates = [task for task in tasks if not task[2] and
                  ((task[4] and task[4] <= today_iso) or (not task[4] and task[3] == "high"))]
    candidates.sort(key=lambda task: (
        0 if task[4] and task[4] < today_iso else 1 if task[4] else 2,
        priority.get(task[3], 1), task[4] or "9999-12-31", task[0],
    ))
    def clock(value):
        return "{:02d}:{:02d}".format(value // 60, value % 60)

    lines = ["🕘 Расписание {}–{} · {}".format(clock(start), clock(end), today.strftime("%d.%m.%Y"))]
    cursor, chosen, skipped, unknown = start, 0, [], []
    for task in candidates:
        estimate = task[5]
        if estimate is None:
            unknown.append(task)
            continue
        pause = break_minutes if chosen else 0
        if cursor + pause + estimate > end:
            skipped.append(task)
            continue
        if pause:
            lines.append("☕ {}–{} Перерыв".format(clock(cursor), clock(cursor + pause)))
            cursor += pause
        lines.append("• {}–{} {} (~{} мин.)".format(
            clock(cursor), clock(cursor + estimate), describe_task(task, today), estimate
        ))
        cursor += estimate
        chosen += 1
    if not chosen:
        lines.append("Нет срочных задач с известной длительностью, помещающихся в это окно.")
    lines.append("Занято: {} мин. · Свободно: {} мин.".format(cursor - start, end - cursor))
    if skipped:
        lines.append("Не поместились: " + ", ".join("#{}".format(task[0]) for task in skipped[:12]))
    if unknown:
        lines.append("Без оценки времени: " + ", ".join("#{}".format(task[0]) for task in unknown[:12]))
    lines.append("Это предложение; задачи и сроки в базе не изменены.")
    return "\n".join(lines)
