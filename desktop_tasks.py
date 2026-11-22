"""Managed lifecycle for non-UI background tasks used by the desktop app."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TaskHandle:
    task_id: int
    name: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    done_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    state: str = "pending"
    result: Any = None
    error: BaseException | None = None

    @property
    def is_alive(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def cancel(self) -> bool:
        if self.done_event.is_set() or self.cancel_event.is_set():
            return False
        self.cancel_event.set()
        return True

    def wait(self, timeout: float | None = None) -> bool:
        return self.done_event.wait(timeout)


class DesktopTaskManager:
    """Owns task threads, cooperative cancellation and deterministic cleanup."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[int, TaskHandle] = {}
        self._next_id = 1
        self._shutting_down = False

    def start(self, name: str, target: Callable[..., Any], *args: Any,
              on_error: Callable[[TaskHandle, BaseException], None] | None = None,
              daemon: bool = True, **kwargs: Any) -> TaskHandle:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Task name must be a non-empty string.")
        if not callable(target):
            raise TypeError("Task target must be callable.")
        with self._lock:
            if self._shutting_down:
                raise RuntimeError("Task manager is shutting down.")
            handle = TaskHandle(self._next_id, name)
            self._next_id += 1

            def run() -> None:
                handle.state = "running"
                try:
                    if handle.cancel_event.is_set():
                        handle.state = "cancelled"
                        return
                    handle.result = target(*args, cancel_event=handle.cancel_event, **kwargs)
                    handle.state = "cancelled" if handle.cancel_event.is_set() else "completed"
                except BaseException as exc:
                    handle.error = exc
                    handle.state = "cancelled" if handle.cancel_event.is_set() else "failed"
                    if on_error is not None and not handle.cancel_event.is_set():
                        try:
                            on_error(handle, exc)
                        except Exception:
                            pass
                finally:
                    handle.done_event.set()

            thread = threading.Thread(target=run, name=f"sherlock-{name}-{handle.task_id}", daemon=daemon)
            handle.thread = thread
            self._tasks[handle.task_id] = handle
            try:
                thread.start()
            except RuntimeError:
                self._tasks.pop(handle.task_id, None)
                raise
            return handle

    def get(self, task_id: int) -> TaskHandle | None:
        with self._lock:
            return self._tasks.get(task_id)

    def active(self) -> tuple[TaskHandle, ...]:
        with self._lock:
            return tuple(task for task in self._tasks.values() if not task.done_event.is_set())

    def active_count(self) -> int:
        return len(self.active())

    def cancel(self, task_id: int) -> bool:
        task = self.get(task_id)
        return task.cancel() if task else False

    def cancel_all(self) -> int:
        return sum(1 for task in self.active() if task.cancel())

    def wait_for_all(self, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        for task in self.active():
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if not task.wait(remaining):
                return False
        return self.active_count() == 0

    def shutdown(self, wait: bool = True, timeout: float | None = None) -> bool:
        with self._lock:
            self._shutting_down = True
        self.cancel_all()
        return self.wait_for_all(timeout) if wait else self.active_count() == 0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            tasks = tuple(self._tasks.values())
            shutting_down = self._shutting_down
        return {
            "shutting_down": shutting_down,
            "active": [{"id": task.task_id, "name": task.name, "state": task.state}
                       for task in tasks if not task.done_event.is_set()],
            "completed": sum(1 for task in tasks if task.done_event.is_set()),
        }
