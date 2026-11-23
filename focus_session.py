"""In-memory focus timer driven by monotonic time; no background processes."""
import time


class FocusSession:
    def __init__(self):
        self.task_id = None
        self.title = ""
        self.started_at = None
        self.elapsed = 0.0

    @property
    def active(self):
        return self.task_id is not None

    @property
    def paused(self):
        return self.active and self.started_at is None

    def start(self, task_id, title, now=None):
        if self.active:
            raise ValueError("Сначала заверши текущую сессию.")
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise ValueError("Некорректная задача.")
        self.task_id = task_id
        self.title = str(title)[:300]
        self.elapsed = 0.0
        self.started_at = time.monotonic() if now is None else now

    def seconds(self, now=None):
        if not self.active:
            return 0
        moment = time.monotonic() if now is None else now
        return max(0, int(self.elapsed + (moment - self.started_at if self.started_at is not None else 0)))

    def pause(self, now=None):
        if not self.active or self.paused:
            raise ValueError("Нет работающего таймера.")
        moment = time.monotonic() if now is None else now
        self.elapsed += max(0, moment - self.started_at)
        self.started_at = None

    def resume(self, now=None):
        if not self.paused:
            raise ValueError("Нет приостановленного таймера.")
        self.started_at = time.monotonic() if now is None else now

    def finish(self, now=None):
        if not self.active:
            raise ValueError("Нет активной сессии.")
        result = self.task_id, self.title, self.seconds(now)
        self.task_id, self.title, self.started_at, self.elapsed = None, "", None, 0.0
        return result
