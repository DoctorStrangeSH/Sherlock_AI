import os
import tempfile
import unittest

from database import Database


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_history_scoped_to_owner(self):
        self.db.add_ai_exchange(1, "Привет", "Здравствуй!")
        self.db.add_ai_exchange(2, "Секрет", "Ответ")
        self.assertEqual(self.db.get_ai_history(1), [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуй!"},
        ])
        self.assertEqual(len(self.db.get_ai_history(2)), 2)

    def test_bounded_history_and_forget(self):
        for index in range(65):
            self.db.add_ai_exchange(1, str(index), "ok")
        self.assertEqual(len(self.db.get_ai_history(1, 200)), 30)
        stored = self.db.conn.execute(
            "SELECT COUNT(*) FROM ai_dialogue WHERE owner_id=1"
        ).fetchone()[0]
        self.assertEqual(stored, 100)
        self.assertEqual(self.db.clear_ai_history(1), 100)
        self.assertEqual(self.db.get_ai_history(1), [])

    def test_forget_does_not_delete_other_owner(self):
        self.db.add_ai_exchange(1, "a", "b")
        self.db.add_ai_exchange(2, "c", "d")
        self.db.clear_ai_history(1)
        self.assertEqual(len(self.db.get_ai_history(2)), 2)


if __name__ == "__main__":
    unittest.main()
