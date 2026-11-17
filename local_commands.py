"""Conservative local-command recognition; no model output can invoke tools."""
import re

RECENT = re.compile(
    r"^(?:покажи|найди|выведи)\s+(?:мне\s+)?"
    r"(?:последние|недавние|недавно\s+измен[её]нные)\s+"
    r"(?:файлы|документы)(?:\s+в\s+(?:выбранной|этой)\s+папке)?[.!?]?$",
    re.IGNORECASE,
)
NOTE = re.compile(r"^(?:создай|запиши|добавь)\s+заметку\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
TASK_CREATE = re.compile(r"^(?:создай|добавь|запиши)\s+задачу\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
TASK_TODAY = re.compile(r"^(?:покажи|выведи)\s+(?:мои\s+)?задачи\s+на\s+сегодня[.!?]?$", re.IGNORECASE)
TASK_OVERDUE = re.compile(r"^(?:покажи|выведи)\s+(?:мои\s+)?просроченные\s+задачи[.!?]?$", re.IGNORECASE)
TASK_DUE = re.compile(r"^(?:установи|поставь|измени)\s+срок\s+задачи\s+#?(\d{1,9})\s*:\s*(\d{4}-\d{2}-\d{2})[.!?]?$", re.IGNORECASE)
TASK_PRIORITY = re.compile(r"^(?:установи|поставь|измени)\s+приоритет\s+задачи\s+#?(\d{1,9})\s*:\s*(низкий|обычный|высокий)[.!?]?$", re.IGNORECASE)
REMINDER_SNOOZE = re.compile(r"^(?:отложи|перенеси)\s+напоминание\s+(?:по\s+задаче\s+)?#?(\d{1,9})\s+на\s+(\d{1,4})\s+(минут(?:у|ы)?|час(?:а|ов)?)\s*[.!?]?$", re.IGNORECASE)
PLAN_SAVE = re.compile(r"^(?:сохрани|запомни)\s+(?:это\s+)?расписание[.!?]?$", re.IGNORECASE)
PLAN_NOW = re.compile(r"^(?:что\s+(?:у\s+меня\s+)?сейчас\s+по\s+расписанию|покажи\s+текущую\s+задачу)[.!?]?$", re.IGNORECASE)
PLAN_HISTORY = re.compile(r"^(?:покажи|открой|выведи)\s+(?:мою\s+)?историю\s+расписаний[.!?]?$", re.IGNORECASE)
PLAN_OPEN = re.compile(r"^(?:покажи|открой)\s+(?:сохран[её]нное\s+)?расписание\s+#?(\d{1,9})[.!?]?$", re.IGNORECASE)
PLAN_SHOW = re.compile(r"^(?:покажи|открой)\s+(?:моё\s+)?сохран[её]нное\s+расписание[.!?]?$", re.IGNORECASE)
TASK_SCHEDULE = re.compile(
    r"^(?:составь|сделай|предложи)\s+расписание\s+с\s+(\d{2}:\d{2})\s+на\s+"
    r"(\d{1,4})\s+(минут(?:у|ы)?|час(?:а|ов)?)"
    r"(?:\s+с\s+перерывом\s+(\d{1,2})\s+минут(?:у|ы)?)?[.!?]?$",
    re.IGNORECASE,
)
TASK_ESTIMATE = re.compile(r"^(?:установи|измени|поставь)\s+длительность\s+задачи\s+#?(\d{1,9})\s*:\s*(\d{1,4})\s+(минут(?:у|ы)?|час(?:а|ов)?)[.!?]?$", re.IGNORECASE)
TASK_BUDGET = re.compile(r"^(?:составь|предложи|сделай)\s+(?:мне\s+)?план\s+на\s+сегодня\s+на\s+(\d{1,4})\s+(минут(?:у|ы)?|час(?:а|ов)?)[.!?]?$", re.IGNORECASE)
TASK_DAY_PARTS = re.compile(r"^(?:распредели|раздели|разбей)\s+(?:мои\s+)?задачи\s+(?:на\s+сегодня|на\s+утро\s*,?\s*день\s*(?:и\s*)?вечер)[.!?]?$", re.IGNORECASE)
TASK_PLAN_TODAY = re.compile(r"^(?:составь|покажи|предложи|сделай)\s+(?:мне\s+)?план\s+на\s+сегодня[.!?]?$", re.IGNORECASE)
TASK_PLAN_WEEK = re.compile(r"^(?:составь|покажи|предложи|сделай)\s+(?:мне\s+)?план\s+на\s+(?:неделю|7\s+дней)[.!?]?$", re.IGNORECASE)
TASK_LIST = re.compile(r"^(?:покажи|выведи)\s+(?:мои\s+)?задачи[.!?]?$", re.IGNORECASE)
TASK_DONE = re.compile(r"^(?:выполни|заверши|отметь\s+выполненной)\s+задачу\s+#?(\d{1,9})[.!?]?$", re.IGNORECASE)
SEARCH = re.compile(
    r"^(?:найди|поищи|отыщи)\s+(?:мне\s+)?(.+?)\s+"
    r"в\s+(?:выбранной|этой)\s+папке[.!?]?$",
    re.IGNORECASE,
)


def parse_local_command(text):
    """Return (kind, query) for unambiguous commands, otherwise None."""
    if not isinstance(text, str) or len(text) > 1100:
        return None
    value = text.strip()
    note = NOTE.fullmatch(value)
    if note:
        content = note.group(1).strip()
        if 1 <= len(content) <= 1000:
            return ("save_note", content)
    task = TASK_CREATE.fullmatch(value)
    if task:
        title = task.group(1).strip()
        if 1 <= len(title) <= 300:
            return ("create_task", title)
    if PLAN_SAVE.fullmatch(value):
        return ("save_schedule", "")
    if PLAN_SHOW.fullmatch(value):
        return ("show_saved_schedule", "")
    if PLAN_NOW.fullmatch(value):
        return ("current_schedule_slot", "")
    if PLAN_HISTORY.fullmatch(value):
        return ("list_saved_schedules", "")
    selected_plan = PLAN_OPEN.fullmatch(value)
    if selected_plan and int(selected_plan.group(1)) > 0:
        return ("open_saved_schedule", int(selected_plan.group(1)))
    schedule = TASK_SCHEDULE.fullmatch(value)
    if schedule:
        amount = int(schedule.group(2))
        duration = amount * 60 if schedule.group(3).lower().startswith("час") else amount
        pause = int(schedule.group(4)) if schedule.group(4) else 10
        start = schedule.group(1)
        if 15 <= duration <= 1440 and 0 <= pause <= 60:
            return ("timed_schedule", (start, duration, pause))
    estimate = TASK_ESTIMATE.fullmatch(value)
    if estimate:
        task_id = int(estimate.group(1))
        count = int(estimate.group(2))
        minutes = count * 60 if estimate.group(3).lower().startswith("час") else count
        if task_id > 0 and 5 <= minutes <= 1440:
            return ("set_task_estimate", (task_id, minutes))
    budget = TASK_BUDGET.fullmatch(value)
    if budget:
        count = int(budget.group(1))
        minutes = count * 60 if budget.group(2).lower().startswith("час") else count
        if 15 <= minutes <= 1440:
            return ("plan_budget", minutes)
    if TASK_DAY_PARTS.fullmatch(value):
        return ("plan_day_parts", "")
    if TASK_PLAN_TODAY.fullmatch(value):
        return ("plan_today", "")
    if TASK_PLAN_WEEK.fullmatch(value):
        return ("plan_week", "")
    if TASK_TODAY.fullmatch(value):
        return ("tasks_today", "")
    if TASK_OVERDUE.fullmatch(value):
        return ("tasks_overdue", "")
    due = TASK_DUE.fullmatch(value)
    if due and int(due.group(1)) > 0:
        return ("set_task_due", (int(due.group(1)), due.group(2)))
    priority = TASK_PRIORITY.fullmatch(value)
    if priority and int(priority.group(1)) > 0:
        return ("set_task_priority", (int(priority.group(1)), priority.group(2).lower()))
    reminder = REMINDER_SNOOZE.fullmatch(value)
    if reminder:
        task_id = int(reminder.group(1))
        duration = int(reminder.group(2))
        minutes = duration * 60 if reminder.group(3).lower().startswith("час") else duration
        if task_id > 0 and 5 <= minutes <= 1440:
            return ("snooze_reminder", (task_id, minutes))
    if TASK_LIST.fullmatch(value):
        return ("list_tasks", "")
    done = TASK_DONE.fullmatch(value)
    if done:
        number = int(done.group(1))
        if number > 0:
            return ("complete_task", number)
    if RECENT.fullmatch(value):
        return ("recent", "")
    match = SEARCH.fullmatch(value)
    if match:
        query = match.group(1).strip().strip("«»\"'")
        if 1 <= len(query) <= 120:
            return ("search", query)
    return None
