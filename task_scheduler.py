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

def describe_current_slot(plan_text, plan_date, at=None):
    """Read the current time block from a generated schedule; no task writes."""
    import re
    from datetime import datetime

    if not isinstance(plan_text, str) or not isinstance(plan_date, str):
        raise ValueError("Некорректное расписание.")
    today = datetime.now()
    at = at or today
    if not isinstance(at, datetime):
        raise ValueError("Некорректное время.")
    if plan_date != at.date().isoformat():
        return "Последнее сохранённое расписание относится к другой дате. Составь новое на сегодня."

    header = re.search(r"^🕘 Расписание (\d{2}:\d{2})–(\d{2}:\d{2}) · (\d{2}\.\d{2}\.\d{4})$", plan_text, re.MULTILINE)
    if not header or header.group(3) != at.strftime("%d.%m.%Y"):
        return "Не удалось распознать сохранённое расписание. Составь новое."
    def minutes(clock):
        hour, minute = map(int, clock.split(":"))
        return hour * 60 + minute if hour < 24 and minute < 60 else None
    start, end = minutes(header.group(1)), minutes(header.group(2))
    if start is None or end is None or start >= end:
        return "Не удалось распознать время расписания."
    now = at.hour * 60 + at.minute
    if now < start:
        return f"Рабочий план ещё не начался: старт в {header.group(1)}."
    if now >= end:
        return f"Запланированное время закончилось в {header.group(2)}."

    slots = []
    for line in plan_text.splitlines():
        match = re.fullmatch(r"(?:•|☕) (\d{2}:\d{2})–(\d{2}:\d{2}) (.+)", line)
        if not match:
            continue
        left, right = minutes(match.group(1)), minutes(match.group(2))
        if left is None or right is None or left >= right or left < start or right > end:
            continue
        slots.append((left, right, line))
    for left, right, line in slots:
        if left <= now < right:
            return "Сейчас по расписанию:\n" + line
    upcoming = [line for left, _, line in slots if left > now]
    if upcoming:
        return "Сейчас свободное окно. Следующий блок:\n" + upcoming[0]
    return "В расписании сейчас свободное время до " + header.group(2) + "."


def shift_saved_schedule(plan_text, plan_date, delay_minutes, today=None):
    """Preview a delayed schedule without changing database records or tasks."""
    import re
    from datetime import datetime
    today = today or datetime.now().date()
    if not isinstance(delay_minutes, int) or isinstance(delay_minutes, bool) or not 5 <= delay_minutes <= 180:
        raise ValueError("Задержка должна быть от 5 до 180 минут.")
    if plan_date != today.isoformat():
        raise ValueError("Перестроить можно только расписание на сегодня.")
    header = re.search(
        r"^🕘 Расписание (\d{2}:\d{2})–(\d{2}:\d{2}) · (\d{2}\.\d{2}\.\d{4})$",
        plan_text, re.MULTILINE,
    )
    if not header or header.group(3) != today.strftime("%d.%m.%Y"):
        raise ValueError("Сохранённое расписание имеет неизвестный формат.")
    def shifted(value):
        hour, minute = map(int, value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("Некорректное время расписания.")
        new_minutes = hour * 60 + minute + delay_minutes
        if new_minutes > 1440:
            raise ValueError("После задержки расписание выходит за полночь.")
        return f"{new_minutes // 60:02d}:{new_minutes % 60:02d}"
    shifted(header.group(2))  # Validate entire window before transforming it.
    def change_time(match):
        return shifted(match.group(1)) + "–" + shifted(match.group(2))
    shifted_lines = []
    for line in plan_text.splitlines():
        if line.startswith("🕘 Расписание "):
            line = re.sub(r"\b(\d{2}:\d{2})–(\d{2}:\d{2})\b", change_time, line, count=1)
        elif line.startswith(("• ", "☕ ")):
            line = re.sub(r"\b(\d{2}:\d{2})–(\d{2}:\d{2})\b", change_time, line, count=1)
        shifted_lines.append(line)
    return ("\n".join(shifted_lines) +
            f"\nПредпросмотр: все блоки сдвинуты на {delay_minutes} мин. "
            "Задачи не изменены; для сохранения напиши «Сохрани расписание».")
