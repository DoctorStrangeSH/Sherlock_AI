"""Read-only folder search boundaries."""
import tempfile
from pathlib import Path
import unittest
from local_folder_search import search_text_folder, MAX_FILES


class FolderSearchTests(unittest.TestCase):
    def test_content_and_name_search(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "guide.md").write_text("Инструкция по установке", encoding="utf-8")
            (root / "project.txt").write_text("Другие сведения", encoding="utf-8")
            result = search_text_folder(root, "установке")
            self.assertEqual(len(result["matches"]), 1)
            self.assertIn("guide.md", result["matches"][0]["path"])
            self.assertEqual(len(search_text_folder(root, "project")["matches"]), 1)

    def test_ignores_hidden_and_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".secret.txt").write_text("секретный", encoding="utf-8")
            (root / "binary.txt").write_bytes("секретный".encode("utf-8") + b"\x00")
            self.assertFalse(search_text_folder(root, "секретный")["matches"])

    def test_cancellation_is_checked_during_scan(self):
        class CancelAfterChecks:
            def __init__(self):
                self.checks = 0
            def is_set(self):
                self.checks += 1
                return self.checks >= 3

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(5):
                (root / f"file{index}.txt").write_text("ordinary text", encoding="utf-8")
            with self.assertRaises(InterruptedError):
                search_text_folder(root, "missing", cancel_event=CancelAfterChecks())

    def test_query_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            for text in ("", " " * 4, "a" * 121):
                with self.assertRaises(ValueError):
                    search_text_folder(temp, text)

    def test_bounded_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for i in range(MAX_FILES + 4):
                (root / f"doc{i:03}.txt").write_text("нет", encoding="utf-8")
            result = search_text_folder(root, "невозможный")
            self.assertEqual(result["checked"], MAX_FILES)
            self.assertTrue(result["limit_reached"])


if __name__ == "__main__":
    unittest.main()
