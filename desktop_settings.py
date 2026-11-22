"""Validated local settings for the Sherlock AI desktop application."""

import json
from pathlib import Path

from task_reminders import valid_reminder_time


DEFAULT_SETTINGS = {
    "model": "Авто",
    "tone": "Тёплый",
    "reminder_time": "09:00",
    "reminders_enabled": False,
    "performance": "Быстро",
}

_ALLOWED_TONES = {"Тёплый", "Краткий", "Деловой"}
_ALLOWED_PERFORMANCE = {"Быстро", "Баланс", "Качество"}


def load_desktop_settings(path):
    """Load and validate preferences; malformed or missing files use safe defaults."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    model = payload.get("model", DEFAULT_SETTINGS["model"])
    tone = payload.get("tone", DEFAULT_SETTINGS["tone"])
    reminder_time = payload.get("reminder_time", DEFAULT_SETTINGS["reminder_time"])
    reminders_enabled = payload.get("reminders_enabled", DEFAULT_SETTINGS["reminders_enabled"])
    performance = payload.get("performance", DEFAULT_SETTINGS["performance"])

    return {
        "model": model if isinstance(model, str) and model.strip() else DEFAULT_SETTINGS["model"],
        "tone": tone if isinstance(tone, str) and tone in _ALLOWED_TONES else DEFAULT_SETTINGS["tone"],
        "reminder_time": reminder_time if valid_reminder_time(reminder_time) else DEFAULT_SETTINGS["reminder_time"],
        "reminders_enabled": reminders_enabled is True,
        "performance": performance if isinstance(performance, str) and performance in _ALLOWED_PERFORMANCE else DEFAULT_SETTINGS["performance"],
    }


def save_desktop_settings(path, settings):
    """Persist only supported preference fields as UTF-8 JSON."""
    values = {
        "model": settings.get("model", DEFAULT_SETTINGS["model"]),
        "tone": settings.get("tone", DEFAULT_SETTINGS["tone"]),
        "reminder_time": settings.get("reminder_time", DEFAULT_SETTINGS["reminder_time"]),
        "reminders_enabled": settings.get("reminders_enabled", False) is True,
        "performance": settings.get("performance", DEFAULT_SETTINGS["performance"]),
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
