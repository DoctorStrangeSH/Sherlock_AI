"""Ephemeral, bounded, single-use Telegram reply drafts.

Drafts never send themselves. A separately authorized owner command must
consume a draft before the caller may send it.
"""

from dataclasses import dataclass, replace
import time


MAX_DRAFTS = 20
TTL_SECONDS = 30 * 60
MAX_REPLY_LENGTH = 2500


@dataclass(frozen=True)
class PendingDraft:
    draft_id: int
    recipient_id: int
    recipient_name: str
    reply: str
    created_at: float


class DraftQueue:
    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._items: dict[int, PendingDraft] = {}
        self._next_id = 1

    def _expire(self):
        now = self._clock()
        for draft_id, draft in list(self._items.items()):
            if now - draft.created_at >= TTL_SECONDS:
                del self._items[draft_id]

    def add(self, recipient_id: int, recipient_name: str, reply: str) -> PendingDraft:
        self._expire()
        reply = reply.strip()
        if not recipient_id or recipient_id <= 0:
            raise ValueError("Неизвестный адресат")
        if not reply or len(reply) > MAX_REPLY_LENGTH:
            raise ValueError("Черновик пустой или слишком длинный")
        if len(self._items) >= MAX_DRAFTS:
            oldest = next(iter(self._items))
            del self._items[oldest]
        draft = PendingDraft(self._next_id, recipient_id, recipient_name[:80],
                             reply, self._clock())
        self._items[draft.draft_id] = draft
        self._next_id += 1
        return draft

    def peek(self, draft_id: int):
        self._expire()
        return self._items.get(draft_id)

    def edit(self, draft_id: int, text: str, *, enabled: bool, allowed_ids) -> PendingDraft | None:
        """Owner-edited draft retains its recipient, ID and original expiry time."""
        self._expire()
        old = self._items.get(draft_id)
        if not (old and enabled and old.recipient_id in allowed_ids):
            return None
        text = text.strip()
        if not text or len(text) > MAX_REPLY_LENGTH:
            raise ValueError("Текст ответа должен содержать от 1 до 2500 символов")
        edited = replace(old, reply=text)
        self._items[draft_id] = edited
        return edited

    def cancel(self, draft_id: int) -> bool:
        self._expire()
        return self._items.pop(draft_id, None) is not None

    def take_for_send(self, draft_id: int, *, enabled: bool, allowed_ids) -> PendingDraft | None:
        """Consume only when still enabled and recipient still allowlisted."""
        self._expire()
        draft = self._items.get(draft_id)
        if not (draft and enabled and draft.recipient_id in allowed_ids):
            return None
        return self._items.pop(draft_id)

    def clear(self):
        self._items.clear()
