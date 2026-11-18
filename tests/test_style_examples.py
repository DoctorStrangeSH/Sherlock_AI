import unittest

from style_examples import (
    add_example, delete_example, valid_examples, examples_context,
    MAX_EXAMPLES,
)


class StyleExamplesTests(unittest.TestCase):
    def test_owner_examples_are_bounded(self):
        examples = []
        for i in range(MAX_EXAMPLES):
            examples = add_example(examples, f"Обычно я пишу вот так: пример {i}")
        self.assertEqual(len(examples), MAX_EXAMPLES)
        with self.assertRaises(ValueError):
            add_example(examples, "Ещё один пример моего общения")

    def test_delete_and_deduplication(self):
        original = "Привет, давай созвонимся чуть позже :)"
        examples = add_example([], original)
        with self.assertRaises(ValueError):
            add_example(examples, original)
        self.assertEqual(delete_example(examples, 1), [])
        with self.assertRaises(ValueError):
            delete_example(examples, 3)

    def test_only_valid_samples_reach_prompt(self):
        samples = ["Добрый вечер! Как твои дела?", 123, "x"]
        self.assertEqual(len(valid_examples(samples)), 1)
        prompt = examples_context(samples)
        self.assertIn("ориентир только по стилю", prompt)
        self.assertNotIn("123", prompt)

    def test_unexpected_store_types_are_ignored(self):
        self.assertEqual(valid_examples(None), [])
        self.assertEqual(examples_context({}), "")


if __name__ == "__main__":
    unittest.main()
