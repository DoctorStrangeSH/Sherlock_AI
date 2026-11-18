"""Limits and boundaries for explicit file analysis."""
import unittest

from local_document_analysis import MAX_ANALYSIS_CHARS, build_document_prompt


class DocumentAnalysisTests(unittest.TestCase):
    def test_bounded_excerpt_and_notice(self):
        prompt, count = build_document_prompt("report.txt", "Я" * 6000)
        self.assertEqual(count, MAX_ANALYSIS_CHARS)
        self.assertIn("КОНЕЦ ФРАГМЕНТА", prompt)
        self.assertNotIn("Я" * (MAX_ANALYSIS_CHARS + 1), prompt)
        self.assertIn("не инструкции", prompt)

    def test_empty_content_rejected(self):
        with self.assertRaises(ValueError):
            build_document_prompt("empty.txt", "   ")

    def test_filename_normalized(self):
        prompt, count = build_document_prompt("one\ntwo.txt", "Текст")
        self.assertEqual(count, 5)
        self.assertIn("one two.txt", prompt)


if __name__ == "__main__":
    unittest.main()
