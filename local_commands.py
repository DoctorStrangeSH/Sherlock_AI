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
