"""Small, conservative detector for owner-requested memory saving.

This does not call a model and never persists anything by itself.
"""
import re

_PREFIX = re.compile(r"^\s*запомни(?:,|\s+)(?:что\s+)?", re.IGNORECASE)
_SENSITIVE = re.compile(
    r"парол|password|api[_ -]?key|api[_ -]?hash|токен|token|секрет|secret|"
    r"код\s+(?:входа|подтверждения|из\s+смс)|2fa|otp|private\s+key",
    re.IGNORECASE,
)


def proposed_memory(message: str) -> str | None:
    """Return a proposed memory only for explicit, non-sensitive Russian requests."""
    if not isinstance(message, str):
        return None
    match = _PREFIX.match(message)
    if not match:
        return None
    fact = message[match.end():].strip().strip(".!? ")
    if not fact or len(fact) > 500 or _SENSITIVE.search(fact):
        return None
    return fact
