"""Tests for the Tk-independent local generation worker and cancellation."""

import asyncio
import queue
import threading
import unittest

from desktop_generation import CANCELLED_ANSWER, GenerationWorker
from local_ai import GenerationCancelled


class FakeResponse:
    def __init__(self):
        self.closed = threading.Event()

    def close(self):
        self.closed.set()


class GenerationWorkerTests(unittest.TestCase):
    def test_streamed_chunks_and_final_answer_are_queued(self):
        async def fake_ask(question, **kwargs):
            kwargs["on_chunk"]("Привет")
            kwargs["on_chunk"]("!")
            return "Привет!"

        events = queue.Queue()
        worker = GenerationWorker(events, ask=fake_ask)
        thread = worker.start("Привет?", [], "warm", "test-model", "Быстро", [])
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(events.get_nowait(), ("chunk", "Привет"))
        self.assertEqual(events.get_nowait(), ("chunk", "!"))
        self.assertEqual(events.get_nowait(), ("answer", "Привет?", "Привет!"))
        self.assertFalse(worker.is_running)

    def test_generation_failure_returns_safe_error_event(self):
        async def failing_ask(_question, **_kwargs):
            raise RuntimeError("private internal detail")

        events = queue.Queue()
        worker = GenerationWorker(events, ask=failing_ask)
        thread = worker.start("Вопрос", [], "warm", None, "Баланс", [])
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(
            events.get_nowait(),
            ("answer", "Вопрос", "Не удалось получить ответ. Проверь подключение к Ollama."),
        )
        self.assertTrue(events.empty())

    def test_worker_rejects_overlapping_generation(self):
        gate = threading.Event()

        async def waiting_ask(_question, **_kwargs):
            await asyncio.to_thread(gate.wait, 2)
            return "готово"

        events = queue.Queue()
        worker = GenerationWorker(events, ask=waiting_ask)
        thread = worker.start("Первый", [], "warm", None, "Баланс", [])
        try:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                worker.start("Второй", [], "warm", None, "Баланс", [])
        finally:
            gate.set()
            thread.join(timeout=2)

    def test_cancel_closes_active_response_and_reports_cancelled(self):
        response = FakeResponse()
        events = queue.Queue()
        started = threading.Event()

        async def cancellable_ask(_question, **kwargs):
            kwargs["on_response"](response)
            started.set()
            await asyncio.to_thread(response.closed.wait, 2)
            if kwargs["cancel_event"].is_set():
                raise GenerationCancelled()
            return "слишком поздно"

        worker = GenerationWorker(events, ask=cancellable_ask)
        thread = worker.start("Останови", [], "warm", None, "Баланс", [])
        self.assertTrue(started.wait(1))
        self.assertTrue(worker.cancel())
        self.assertTrue(response.closed.wait(1))
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(events.get_nowait(), ("answer", "Останови", CANCELLED_ANSWER))
        self.assertFalse(worker.is_running)
        self.assertFalse(worker.cancel())

    def test_cancel_before_response_arrives_closes_it_when_attached(self):
        response = FakeResponse()
        events = queue.Queue()
        allow_response = threading.Event()

        async def delayed_ask(_question, **kwargs):
            await asyncio.to_thread(allow_response.wait, 2)
            kwargs["on_response"](response)
            if kwargs["cancel_event"].is_set():
                raise GenerationCancelled()
            return "unexpected"

        worker = GenerationWorker(events, ask=delayed_ask)
        thread = worker.start("Останови до подключения", [], "warm", None, "Баланс", [])
        self.assertTrue(worker.cancel())
        allow_response.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertTrue(response.closed.is_set())
        self.assertEqual(events.get_nowait(), ("answer", "Останови до подключения", CANCELLED_ANSWER))


if __name__ == "__main__":
    unittest.main()
