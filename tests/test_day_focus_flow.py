"""End-to-end checks for the offline day-planning and focus workflow."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from focus_session import FocusSession
from offline_workspace import OfflineWorkspace
from task_scheduler import build_timed_schedule


class DayFocusFlowTests(unittest.TestCase):
    def test_focus_pause_resume_finish_and_saved_statistics(self):
        today = date(2026, 11, 17).isoformat()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "workspace.sqlite3"
            with OfflineWorkspace(path) as workspace:
                task = workspace.add_task("Написать отчёт", "normal", today)
                workspace.update_task_estimate(task, 30)
                timer = FocusSession()
                timer.start(task, "Написать отчёт", now=100.0)
                self.assertEqual(timer.seconds(now=160.0), 60)
                timer.pause(now=160.0)
                self.assertEqual(timer.seconds(now=900.0), 60)
                timer.resume(now=900.0)
                self.assertEqual(timer.seconds(now=1020.0), 180)
                task_id, title, seconds = timer.finish(now=1020.0)
                self.assertFalse(timer.active)
                self.assertEqual((task_id, title, seconds), (task, "Написать отчёт", 180))
                self.assertEqual(workspace.focus_day_summary(today), (0, 0))
                workspace.save_focus_session(task_id, title, seconds, today)
                self.assertEqual(workspace.focus_day_summary(today), (1, 180))
                self.assertEqual(workspace.focus_week_summary(today), (1, 180))
                self.assertEqual(workspace.focus_estimate_comparison(today),
                                 [(task, title, 30, 180)])
            with OfflineWorkspace(path) as reopened:
                self.assertEqual(reopened.focus_day_summary(today), (1, 180))
                self.assertEqual(reopened.recent_focus_sessions(),
                                 [(task, title, 180, today)])

    def test_schedule_is_read_only_and_respects_explicit_estimates(self):
        today = date(2026, 11, 17)
        with TemporaryDirectory() as folder:
            with OfflineWorkspace(Path(folder) / "data.sqlite3") as workspace:
                timed = workspace.add_task("Срочный звонок", "high", today.isoformat())
                unknown = workspace.add_task("Неоценённая задача", "normal", today.isoformat())
                workspace.update_task_estimate(timed, 25)
                before = workspace.list_task_estimates()
                plan = build_timed_schedule(before, "09:00", 60, break_minutes=10, today=today)
                self.assertIn("09:00–09:25", plan)
                self.assertIn(f"Без оценки времени: #{unknown}", plan)
                self.assertEqual(workspace.list_task_estimates(), before)
                self.assertIsNone(workspace.latest_plan())

    def test_deferral_rejects_high_priority_overdue_and_stale_selection_atomically(self):
        today = date(2026, 11, 17)
        day = today.isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()
        with TemporaryDirectory() as folder:
            with OfflineWorkspace(Path(folder) / "data.sqlite3") as workspace:
                normal = workspace.add_task("Можно перенести", "normal", day)
                high = workspace.add_task("Срочно", "high", day)
                overdue = workspace.add_task("Уже просрочено", "low", yesterday)
                self.assertEqual(workspace.defer_nonurgent_tasks(day, [normal]), 1)
                self.assertEqual(dict((row[0], row[4]) for row in workspace.list_task_details())[normal],
                                 tomorrow)
                with self.assertRaises(ValueError):
                    workspace.defer_nonurgent_tasks(day, [normal])
                with self.assertRaises(ValueError):
                    workspace.defer_nonurgent_tasks(day, [high, overdue])
                self.assertEqual(dict((row[0], row[4]) for row in workspace.list_task_details())[high],
                                 day)
                self.assertEqual(dict((row[0], row[4]) for row in workspace.list_task_details())[overdue],
                                 yesterday)
                # A mixed selection cannot partially defer a valid task.
                another = workspace.add_task("Остаётся сегодня", "low", day)
                with self.assertRaises(ValueError):
                    workspace.defer_nonurgent_tasks(day, [another, high])
                self.assertEqual(dict((row[0], row[4]) for row in workspace.list_task_details())[another],
                                 day)


if __name__ == "__main__":
    unittest.main()
