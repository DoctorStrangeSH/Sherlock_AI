"""Explicit action permissions."""
import unittest
from local_action_policy import permission_for, may_execute


class PolicyTests(unittest.TestCase):
    def test_read_only(self):
        self.assertEqual(permission_for("search_files"), "automatic")
        self.assertTrue(may_execute("recent_files"))
        self.assertTrue(may_execute("list_tasks"))

    def test_confirmation(self):
        self.assertEqual(permission_for("save_note"), "confirm")
        self.assertFalse(may_execute("save_note"))
        self.assertTrue(may_execute("save_note", confirmed=True))
        self.assertFalse(may_execute("complete_task"))
        self.assertTrue(may_execute("complete_task", confirmed=True))
        self.assertFalse(may_execute("update_task"))
        self.assertTrue(may_execute("update_task", confirmed=True))

    def test_unknown_and_destructive_denied(self):
        for action in ("delete_file", "shell_command", "unknown", ""):
            self.assertEqual(permission_for(action), "denied")
            self.assertFalse(may_execute(action, confirmed=True))


if __name__ == "__main__":
    unittest.main()
