"""Recent-files inventory tests."""
import tempfile
from pathlib import Path
import os
import unittest

from local_recent_files import recent_text_files, format_recent_file


class RecentFilesTests(unittest.TestCase):
    def test_sorted_by_modified_time(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            old = folder / "old.txt"
            new = folder / "new.md"
            old.write_text("one", encoding="utf-8")
            new.write_text("two", encoding="utf-8")
            os.utime(old, (100000, 100000))
            os.utime(new, (200000, 200000))
            result = recent_text_files(folder)
            self.assertEqual([Path(item["path"]).name for item in result["files"]], ["new.md", "old.txt"])
            self.assertIn("байт", format_recent_file(result["files"][0]))

    def test_skips_hidden_and_unsupported_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / ".hidden.txt").write_text("hidden", encoding="utf-8")
            (folder / "photo.png").write_bytes(b"png")
            self.assertEqual(recent_text_files(folder)["files"], [])

    def test_rejects_non_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                recent_text_files(Path(temp) / "missing")


if __name__ == "__main__":
    unittest.main()
