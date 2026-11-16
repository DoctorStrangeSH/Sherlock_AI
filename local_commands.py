"""Conservative local-command recognition; no model output can invoke tools."""
import re

RECENT = re.compile(
    r"^(?:покажи|найди|выведи)\s+(?:мне\s+)?"
    r"(?:последние|недавние|недавно\s+измен[её]нные)\s+"
    r"(?:файлы|документы)(?:\s+в\s+(?:выбранной|этой)\s+папке)?[.!?]?$",
    re.IGNORECASE,
)
SEARCH = re.compile(
    r"^(?:найди|поищи|отыщи)\s+(?:мне\s+)?(.+?)\s+"
    r"в\s+(?:выбранной|этой)\s+папке[.!?]?$",
    re.IGNORECASE,
)


def parse_local_command(text):
    """Return (kind, query) for unambiguous commands, otherwise None."""
    if not isinstance(text, str) or len(text) > 250:
        return None
    value = text.strip()
    if RECENT.fullmatch(value):
        return ("recent", "")
    match = SEARCH.fullmatch(value)
    if match:
        query = match.group(1).strip().strip("«»\"'")
        if 1 <= len(query) <= 120:
            return ("search", query)
    return None
