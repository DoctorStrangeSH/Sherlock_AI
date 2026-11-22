"""Background worker for local model generation; contains no Tkinter code."""

import asyncio
import queue
import threading
from collections.abc import Callable

from local_ai import ask_local_ai


class GenerationWorker:
    """Run one local AI request on a daemon thread and publish UI-neutral events."""

    def __init__(self, events: queue.Queue, ask: Callable | None = None):
        self.events = events
        self.ask = ask or ask_local_ai
        self.thread: threading.Thread | None = None

    def start(
        self,
        question: str,
        history: list,
        tone: str,
        model: str | None,
        performance: str,
        facts: list[str],
    ) -> threading.Thread:
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("A generation request is already running.")
        self.thread = threading.Thread(
            target=self._run,
            args=(question, history, tone, model, performance, facts),
            daemon=True,
            name="sherlock-ai-generation",
        )
        self.thread.start()
        return self.thread

    def _run(
        self,
        question: str,
        history: list,
        tone: str,
        model: str | None,
        performance: str,
        facts: list[str],
    ) -> None:
        try:
            answer = asyncio.run(
                self.ask(
                    question,
                    history=history,
                    tone=tone,
                    model=model,
                    facts=facts,
                    on_chunk=lambda chunk: self.events.put(("chunk", chunk)),
                    performance=performance,
                )
            )
        except Exception:
            answer = "Не удалось получить ответ. Проверь подключение к Ollama."
        self.thread = None
        self.events.put(("answer", question, answer))
