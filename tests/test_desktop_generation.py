"""Tests for the Tk-independent local generation worker."""

import asyncio
import queue
import unittest

from desktop_generation import GenerationWorker


class GenerationWorkerTests(unittest.TestCase):
    def test_streamed_chunks_and_final_answer_are_queued(self):
        async def fake_ask(question, **kwargs):
            kwargs["on_chunk"]("Привет")
            kwargs["on_chunk(" + " ") if False else kwargs["on_chunk"]("!")
            return "Привет!"

        events = queue.Queue()
        worker = GenerationWorker(events, ask=fake_ask)
        thread = worker.start("Привет?", [], "warm", "test-model", "Быстро", [])
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(events.get_nowait(), ("chunk", "Привет"))
        self.assertEqual(events.get_nowait(), ("chunk", "!"))
        self.assertEqual(events.get_nowait(), ("answer", "Привет?", "Привет!"))
        self.assertTrue(asyncio.iscoroutinefunction(fake_ask))

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
        import threading

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


if __name__ == "__main__":
    unittest.main()
