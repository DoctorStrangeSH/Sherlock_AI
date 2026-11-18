import os
import tempfile
import unittest

from database import Database


class FactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.temp.name, "test.sqlite"))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_explicit_fact_roundtrip(self):
        fact_id = self.db.add_ai_fact(123, "  Я   делаю  игры  ")
        self.assertEqual(self.db.list_ai_facts(123), [(fact_id, "Я делаю игры")])
        self.assertEqual(self.db.list_ai_facts(456), [])
        self.assertFalse(self.db.delete_ai_fact(456, fact_id))
        self.assertTrue(self.db.delete_ai_fact(123, fact_id))

    def test_limits_and_owner_scoped_erasure(self):
        self.db.add_ai_fact(2, "Сохранить")
        for index in range(50):
            self.db.add_ai_fact(1, "Заметка " + str(index))
        with self.assertRaises(ValueError):
            self.db.add_ai_fact(1, "Лимит")
        with self.assertRaises(ValueError):
            self.db.add_ai_fact(1, "x" * 501)
        self.assertEqual(self.db.clear_ai_facts(1), 50)
        self.assertEqual(len(self.db.list_ai_facts(2)), 1)


if __name__ == "__main__":
    unittest.main()
