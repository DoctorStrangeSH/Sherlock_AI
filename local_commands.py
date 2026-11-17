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
