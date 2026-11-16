"""Owner-controlled local assistant memory regression tests."""
import tempfile
from pathlib import Path
import unittest

from offline_workspace import OfflineWorkspace


class MemoryTests(unittest.TestCase):
    def test_explicit_memory_crud(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.sqlite3"
            with OfflineWorkspace(path) as store:
                self.assertEqual(store.list_memories(), [])
                fact_id = store.add_memory("Люблю короткие ответы")
                self.assertEqual(store.list_memories(), [(fact_id, "Люблю короткие ответы")])
                self.assertTrue(store.update_memory(fact_id, "Предпочитаю русский язык"))
                with self.assertRaises(ValueError):
                    store.add_memory(" ")
            with OfflineWorkspace(path) as store:
                self.assertEqual(store.list_memories(), [(fact_id, "Предпочитаю русский язык")])
                self.assertTrue(store.delete_memory(fact_id))
                self.assertEqual(store.list_memories(), [])


if __name__ == "__main__":
    unittest.main()
