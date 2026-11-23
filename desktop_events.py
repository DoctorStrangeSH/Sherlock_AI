"""Thread-safe event delivery and background-operation tracking for desktop UI."""

from __future__ import annotations
import queue
import threading
from collections import Counter
from typing import Any

class DesktopEventBus:
    """FIFO event queue that rejects late events after application shutdown."""
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False
        self._published = self._consumed = self._rejected = 0

    def put(self, event: tuple) -> bool:
        if not isinstance(event, tuple) or not event:
            raise ValueError("Desktop events must be non-empty tuples.")
        with self._lock:
            if self._closed:
                self._rejected += 1
                return False
            self._queue.put(event)
            self._published += 1
            return True

    def publish(self, name: str, *payload: Any) -> bool:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Event name must be a non-empty string.")
        return self.put((name, *payload))

    def get_nowait(self) -> tuple:
        event = self._queue.get_nowait()
        with self._lock:
            self._consumed += 1
        return event

    def drain(self, limit: int = 100) -> list[tuple]:
        if limit < 1:
            return []
        result = []
        for _ in range(limit):
            try:
                result.append(self.get_nowait())
            except queue.Empty:
                break
        return result

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def close(self, discard_pending: bool = False) -> int:
        with self._lock:
            self._closed = True
        discarded = 0
        if discard_pending:
            while True:
                try:
                    self._queue.get_nowait()
                    discarded += 1
                except queue.Empty:
                    break
        return discarded

    def stats(self) -> dict[str, int | bool]:
        with self._lock:
            return {"published": self._published, "consumed": self._consumed,
                    "rejected": self._rejected, "pending": self._queue.qsize(),
                    "closed": self._closed}

class OperationRegistry:
    """Thread-safe counters for named background operations."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: Counter[str] = Counter()
        self._started = self._completed = 0

    def begin(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Operation name must be a non-empty string.")
        with self._lock:
            self._active[name] += 1
            self._started += 1
        return True

    def finish(self, name: str) -> bool:
        with self._lock:
            if self._active[name] <= 0:
                return False
            self._active[name] -= 1
            if self._active[name] == 0:
                del self._active[name]
            self._completed += 1
            return True

    def is_active(self, name: str) -> bool:
        with self._lock:
            return self._active[name] > 0

    def active_count(self) -> int:
        with self._lock:
            return sum(self._active.values())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"active": dict(self._active), "started": self._started,
                    "completed": self._completed}
