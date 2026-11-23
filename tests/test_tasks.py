import os
import tempfile
import unittest

from database import Database


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.temp.name, "test.db"))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_task_lifecycle_and_isolation(self):
        task_id = self.db.add_ai_task(1, "  Сделать   прототип  ")
        self.assertEqual(self.db.list_ai_tasks(1), [(task_id, "Сделать прототип")])
        self.assertEqual(self.db.list_ai_tasks(2), [])
        self.assertFalse(self.db.complete_ai_task(2, task_id))
        self.assertTrue(self.db.complete_ai_task(1, task_id))
        self.assertFalse(self.db.complete_ai_task(1, task_id))
        self.assertEqual(self.db.list_ai_tasks(1), [])
        self.assertEqual(self.db.list_ai_tasks(1, "done"), [(task_id, "Сделать прототип")])
        self.assertFalse(self.db.delete_ai_task(2, task_id))
        self.assertTrue(self.db.delete_ai_task(1, task_id))

    def test_task_input_validation(self):
        for title in ("", " ", "x" * 301):
            with self.assertRaises(ValueError):
                self.db.add_ai_task(1, title)

    def test_open_task_limit(self):
        for i in range(200):
            self.db.add_ai_task(1, "Task " + str(i))
        with self.assertRaises(ValueError):
            self.db.add_ai_task(1, "Extra")


if __name__ == "__main__":
    unittest.main()
