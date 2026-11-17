"""Daily and overdue task classifications."""
from datetime import date
import unittest
from task_overview import task_bucket, filtered_tasks, describe_task


class TaskOverviewTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 17)

    def test_today_overdue_and_done(self):
        tasks = [
            (1, "Сегодня", 0, "normal", "2026-11-17"),
            (2, "Просрочено", 0, "high", "2026-11-16"),
            (3, "Готово", 1, "high", "2026-11-16"),
            (4, "Позже", 0, "low", "2026-11-18"),
            (5, "Без срока", 0, "normal", None),
        ]
        self.assertEqual([task[0] for task in filtered_tasks(tasks, "today", self.today)], [1])
        self.assertEqual([task[0] for task in filtered_tasks(tasks, "overdue", self.today)], [2])
        self.assertEqual(task_bucket(tasks[2], self.today), "done")
        self.assertIn("Просрочено", describe_task(tasks[1], self.today))

    def test_bad_filter(self):
        with self.assertRaises(ValueError):
            filtered_tasks([], "all", self.today)


if __name__ == "__main__":
    unittest.main()
