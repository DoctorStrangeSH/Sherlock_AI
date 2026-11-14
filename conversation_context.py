"""Ephemeral, per-contact context for explicit opt-in Telegram drafts.

Only short text snippets from allowlisted private chats are stored in RAM.
"""

from collections import OrderedDict


MAX_CONTACTS = 30
MAX_MESSAGES = 6
MAX_TEXT_LENGTH = 500


class RecentChatContext:
    def __init__(self):
        self._chats = OrderedDict()

    def add(self, contact_id: int, role: str, text: str) -> None:
        if not isinstance(contact_id, int) or contact_id <= 0:
            return
        if role not in ("owner", "contact") or not isinstance(text, str):
            return
        cleaned = " ".join(text.split())[:MAX_TEXT_LENGTH]
        if not cleaned or cleaned.startswith("."):
            return
        history = self._chats.pop(contact_id, [])
        history.append((role, cleaned))
        self._chats[contact_id] = history[-MAX_MESSAGES:]
        while len(self._chats) > MAX_CONTACTS:
            self._chats.popitem(last=False)

    def recent(self, contact_id: int):
        history = self._chats.get(contact_id, [])
        return list(history)

    def clear(self):
        self._chats.clear()
