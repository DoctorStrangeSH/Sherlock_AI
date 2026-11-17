"""Conservative local-command recognition; no model output can invoke tools."""
import re

RECENT = re.compile(
    r"^(?:покажи|найди|выведи)\s+(?:мне\s+)?"
    r"(?:последние|недавние|недавно\s+измен[её]нные)\s+"
    r"(?:файлы|документы)(?:\s+в\s+(?:выбранной|этой)\s+папке)?[.!?]?$",
    re.IGNORECASE,
)
NOTE = re.compile(r"^(?:создай|запиши|добавь)\s+заметку\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
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
    if RECENT.fullmatch(value):
        return ("recent", "")
    match = SEARCH.fullmatch(value)
    if match:
        query = match.group(1).strip().strip("«»\"'")
        if 1 <= len(query) <= 120:
            return ("search", query)
    return None
