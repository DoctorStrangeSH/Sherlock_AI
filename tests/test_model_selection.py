import unittest
from model_selection import choose_model


class SelectionTests(unittest.TestCase):
    def test_prefers_installed_fast_model(self):
        self.assertEqual(choose_model(["mistral:latest", "qwen3:8b"]), "qwen3:8b")

    def test_falls_back_to_any_installed_model(self):
        self.assertEqual(choose_model(["llama3:latest"]), "llama3:latest")

    def test_explicit_selection(self):
        self.assertEqual(choose_model(["qwen3:8b", "qwen3.5:9b"], "qwen3.5:9b"), "qwen3.5:9b")

    def test_explicit_missing_model_is_reported(self):
        with self.assertRaises(ValueError):
            choose_model(["qwen3:8b"], "not-installed:latest")

    def test_empty_machine_is_reported(self):
        with self.assertRaises(ValueError):
            choose_model([])


if __name__ == "__main__":
    unittest.main()
