"""Background worker for local model generation; contains no Tkinter code."""

import asyncio
import queue
import threading
from collections.abc import Callable

from local_ai import GenerationCancelled, ask_local_ai

CANCELLED_ANSWER = "Генерация остановлена пользователем."


class GenerationWorker:
    """Run one local AI request and publish UI-neutral events."""

    def __init__(self, events: queue.Queue, ask: Callable | None = None):
        self.events = events
        self.ask = ask or ask_local_ai
        self.thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._cancel_event: threading.Event | None = None
        self._response = None

    @property
    def is_running(self) -> bool:
        thread = self.thread
        return thread is not None and thread.is_alive()

    def start(self, question, history, tone, model, performance, facts) -> threading.Thread:
        with self._lock:
            if self.thread is not None and self.thread.is_alive():
                raise RuntimeError("A generation request is already running.")
            cancel_event = threading.Event()
            self._cancel_event = cancel_event
            self._response = None
            self.thread = threading.Thread(
                target=self._run,
                args=(question, history, tone, model, performance, facts, cancel_event),
                daemon=True,
                name="sherlock-ai-generation",
            )
            thread = self.thread
            thread.start()
            return thread

    def cancel(self) -> bool:
        """Request cancellation and close the active HTTP response if available."""
        with self._lock:
            cancel_event = self._cancel_event
            response = self._response
            if cancel_event is None or cancel_event.is_set():
                return False
            cancel_event.set()
        if response is not None:
            try:
                response.close()
            except (OSError, ValueError):
                pass
        return True

    def _set_response(self, response, cancel_event) -> None:
        with self._lock:
            if self._cancel_event is not cancel_event:
                should_close = True
            else:
                self._response = response
                should_close = cancel_event.is_set()
        if should_close and response is not None:
            try:
                response.close()
            except (OSError, ValueError):
                pass

    def _run(self, question, history, tone, model, performance, facts, cancel_event) -> None:
        try:
            answer = asyncio.run(self.ask(
                question,
                history=history,
                tone=tone,
                model=model,
                facts=facts,
                on_chunk=lambda chunk: self.events.put(("chunk", chunk)),
                performance=performance,
                cancel_event=cancel_event,
                on_response=lambda response: self._set_response(response, cancel_event),
            ))
        except GenerationCancelled:
            answer = CANCELLED_ANSWER
        except Exception:
            answer = "Не удалось получить ответ. Проверь подключение к Ollama."
        finally:
            self._set_response(None, cancel_event)
            with self._lock:
                if self._cancel_event is cancel_event:
                    self._cancel_event = None
                    self._response = None
        self.events.put(("answer", question, answer))
