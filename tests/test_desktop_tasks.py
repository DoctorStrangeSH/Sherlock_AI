"""Lifecycle tests for the desktop background task manager."""

import threading
import unittest

from desktop_tasks import DesktopTaskManager


class DesktopTaskManagerTests(unittest.TestCase):
    def test_task_result_and_completion_are_recorded(self):
        manager = DesktopTaskManager()
        task = manager.start("unit", lambda *, cancel_event: 42)
        self.assertTrue(task.wait(1))
        self.assertEqual(task.result, 42)
        self.assertEqual(task.state, "completed")
        self.assertEqual(manager.active_count(), 0)

    def test_cooperative_cancellation_is_observable(self):
        manager = DesktopTaskManager()
        started = threading.Event()

        def work(*, cancel_event):
            started.set()
            cancel_event.wait(2)
            return "stopped"

        task = manager.start("cancel", work)
        self.assertTrue(started.wait(1))
        self.assertTrue(manager.cancel(task.task_id))
        self.assertTrue(task.wait(1))
        self.assertEqual(task.state, "cancelled")
        self.assertFalse(manager.cancel(task.task_id))

    def test_cancel_all_and_wait_for_all(self):
        manager = DesktopTaskManager()
        started = [threading.Event() for _ in range(3)]

        def work(event, *, cancel_event):
            event.set()
            cancel_event.wait(2)

        tasks = [manager.start("batch", work, event) for event in started]
        self.assertTrue(all(event.wait(1) for event in started))
        self.assertEqual(manager.cancel_all(), 3)
        self.assertTrue(manager.wait_for_all(1))
        self.assertTrue(all(task.state == "cancelled" for task in tasks))

    def test_failure_is_recorded_and_reported(self):
        manager = DesktopTaskManager()
        reported = threading.Event()

        def fail(*, cancel_event):
            raise ValueError("expected")

        def on_error(task, error):
            self.assertEqual(task.name, "failure")
            self.assertIsInstance(error, ValueError)
            reported.set()

        task = manager.start("failure", fail, on_error=on_error)
        self.assertTrue(task.wait(1))
        self.assertTrue(reported.is_set())
        self.assertEqual(task.state, "failed")
        self.assertIsInstance(task.error, ValueError)

    def test_shutdown_rejects_new_tasks_and_cancels_active(self):
        manager = DesktopTaskManager()
        started = threading.Event()

        def work(*, cancel_event):
            started.set()
            cancel_event.wait(2)

        task = manager.start("shutdown", work)
        self.assertTrue(started.wait(1))
        self.assertTrue(manager.shutdown(timeout=1))
        self.assertEqual(task.state, "cancelled")
        with self.assertRaisesRegex(RuntimeError, "shutting down"):
            manager.start("late", lambda *, cancel_event: None)

    def test_wait_timeout_does_not_claim_completion(self):
        manager = DesktopTaskManager()
        release = threading.Event()
        task = manager.start("slow", lambda *, cancel_event: release.wait(2))
        self.assertFalse(manager.wait_for_all(timeout=0.01))
        self.assertTrue(task.is_alive)
        release.set()
        self.assertTrue(manager.wait_for_all(timeout=1))

    def test_invalid_task_arguments_are_rejected(self):
        manager = DesktopTaskManager()
        with self.assertRaises(ValueError):
            manager.start("", lambda *, cancel_event: None)
        with self.assertRaises(TypeError):
            manager.start("invalid", None)


if __name__ == "__main__":
    unittest.main()
