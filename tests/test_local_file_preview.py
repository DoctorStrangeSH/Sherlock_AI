"""Read-only local file preview safety limits."""
import tempfile
from pathlib import Path
import unittest

from local_file_preview import MAX_PREVIEW_BYTES, preview_text_file


class LocalPreviewTests(unittest.TestCase):
    def test_text_file_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hello.txt"
            path.write_text("Привет, Шерлок!", encoding="utf-8")
            result = preview_text_file(path)
            self.assertEqual(result["content"], "Привет, Шерлок!")
            self.assertFalse(result["truncated"])

    def test_disallowed_and_binary_files(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "unknown.bin"
            binary.write_bytes(b"test")
            with self.assertRaises(ValueError):
                preview_text_file(binary)
            disguised = Path(folder) / "disguised.txt"
            disguised.write_bytes(b"hello\x00world")
            with self.assertRaises(ValueError):
                preview_text_file(disguised)

    def test_large_preview_is_truncated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large.log"
            path.write_bytes(b"x" * (MAX_PREVIEW_BYTES + 10))
            result = preview_text_file(path)
            self.assertTrue(result["truncated"])
            self.assertEqual(len(result["content"]), MAX_PREVIEW_BYTES)


if __name__ == "__main__":
    unittest.main()
