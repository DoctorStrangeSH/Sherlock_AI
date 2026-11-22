"""Tests for desktop event delivery and operation lifecycle tracking."""
import threading
import unittest
from desktop_events import DesktopEventBus, OperationRegistry

class DesktopEventBusTests(unittest.TestCase):
    def test_publish_and_legacy_put_preserve_fifo_order(self):
        bus = DesktopEventBus()
        self.assertTrue(bus.publish("model", "ready"))
        self.assertTrue(bus.put(("chunk", "hello")))
        self.assertEqual(bus.drain(), [("model", "ready"), ("chunk", "hello")])
        self.assertEqual(bus.pending, 0)
        self.assertEqual(bus.stats()["published"], 2)
        self.assertEqual(bus.stats()["consumed"], 2)

    def test_drain_respects_batch_limit(self):
        bus = DesktopEventBus()
        for index in range(5): bus.publish("item", index)
        self.assertEqual(bus.drain(2), [("item", 0), ("item", 1)])
        self.assertEqual(bus.drain(10), [("item", 2), ("item", 3), ("item", 4)])

    def test_closed_bus_rejects_late_events(self):
        bus = DesktopEventBus()
        bus.publish("before")
        bus.close()
        self.assertFalse(bus.publish("after"))
        self.assertEqual(bus.drain(), [("before",)])
        self.assertEqual(bus.stats()["rejected"], 1)

    def test_close_can_discard_pending_events(self):
        bus = DesktopEventBus()
        bus.publish("one"); bus.publish("two")
        self.assertEqual(bus.close(discard_pending=True), 2)
        self.assertEqual(bus.pending, 0)

    def test_invalid_events_are_rejected(self):
        bus = DesktopEventBus()
        with self.assertRaises(ValueError): bus.put(())
        with self.assertRaises(ValueError): bus.publish("")

class OperationRegistryTests(unittest.TestCase):
    def test_tracks_multiple_operations_and_completion(self):
        registry = OperationRegistry()
        registry.begin("search"); registry.begin("search"); registry.begin("model")
        self.assertEqual(registry.active_count(), 3)
        self.assertTrue(registry.finish("search"))
        self.assertEqual(registry.snapshot()["active"]["search"], 1)
        self.assertTrue(registry.finish("search"))
        self.assertFalse(registry.is_active("search"))
        self.assertFalse(registry.finish("search"))
        self.assertEqual(registry.snapshot()["completed"], 2)

    def test_registry_is_thread_safe(self):
        registry = OperationRegistry()
        workers, iterations = 8, 250
        barrier = threading.Barrier(workers)
        def run():
            barrier.wait()
            for _ in range(iterations):
                registry.begin("parallel"); registry.finish("parallel")
        threads = [threading.Thread(target=run) for _ in range(workers)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=3)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        state = registry.snapshot()
        self.assertEqual(state["started"], workers * iterations)
        self.assertEqual(state["completed"], workers * iterations)
        self.assertEqual(state["active"], {})

if __name__ == "__main__": unittest.main()
