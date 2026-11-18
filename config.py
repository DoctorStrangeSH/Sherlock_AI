"""Конфигурация: секреты поступают только из переменных окружения."""
import os
from datetime import timedelta, timezone

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана переменная {name}. Смотри .env.example")
    return value

API_ID = int(required("TELEGRAM_API_ID"))
API_HASH = required("TELEGRAM_API_HASH")
SESSION_STRING = required("TELEGRAM_SESSION_STRING")
OWNER_ID = int(required("TELEGRAM_OWNER_ID"))
GROUP_ID = int(required("TELEGRAM_GROUP_ID"))
TOPIC_INCOMING = int(os.getenv("TOPIC_INCOMING", "2"))
TOPIC_REMINDERS = int(os.getenv("TOPIC_REMINDERS", "3"))
TOPIC_STATS = int(os.getenv("TOPIC_STATS", "4"))
TOPIC_IMPORTANT = int(os.getenv("TOPIC_IMPORTANT", "5"))
MOSCOW_TZ = timezone(timedelta(hours=3))
FILTER_MODE = os.getenv("FILTER_MODE", "all")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
