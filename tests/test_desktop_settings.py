import json
import tempfile
import unittest
from pathlib import Path

from desktop_settings import DEFAULT_SETTINGS, load_desktop_settings, save_desktop_settings


class DesktopSettingsTests(unittest.TestCase):
    def test_window_metrics_fit_small_screens(self):
        from desktop_settings import desktop_window_metrics

        initial, minimum = desktop_window_metrics(800, 600)
        self.assertEqual(minimum, (760, 520))
        self.assertGreaterEqual(initial[0], minimum[0])
        self.assertGreaterEqual(initial[1], minimum[1])
        self.assertLessEqual(initial[0], 760)
        self.assertLessEqual(initial[1], 520)

    def test_window_metrics_keep_standard_desktop_size(self):
        from desktop_settings import desktop_window_metrics

        self.assertEqual(
            desktop_window_metrics(1920, 1080),
            ((1120, 760), (760, 550)),
        )

    def test_missing_file_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = load_desktop_settings(Path(directory) / "missing.json")
        self.assertEqual(settings, DEFAULT_SETTINGS)

    def test_invalid_json_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(load_desktop_settings(path), DEFAULT_SETTINGS)

    def test_non_object_json_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            self.assertEqual(load_desktop_settings(path), DEFAULT_SETTINGS)

    def test_invalid_values_are_replaced_individually(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "model": "",
                "tone": "unknown",
                "reminder_time": "99:99",
                "reminders_enabled": 1,
                "performance": "turbo",
            }), encoding="utf-8")
            self.assertEqual(load_desktop_settings(path), DEFAULT_SETTINGS)

    def test_wrong_json_value_types_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "tone": ["unexpected"],
                "performance": {"unexpected": True},
            }), encoding="utf-8")
            self.assertEqual(load_desktop_settings(path), DEFAULT_SETTINGS)

    def test_valid_values_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "settings.json"
            expected = {
                "model": "qwen3:8b",
                "tone": "Краткий",
                "reminder_time": "08:30",
                "reminders_enabled": True,
                "performance": "Баланс",
            }
            save_desktop_settings(path, expected)
            self.assertEqual(load_desktop_settings(path), expected)

    def test_only_supported_fields_are_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_desktop_settings(path, {"model": "Авто", "api_key": "must-not-be-saved"})
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("api_key", saved)
        self.assertEqual(set(saved), set(DEFAULT_SETTINGS))


if __name__ == "__main__":
    unittest.main()
