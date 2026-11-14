"""Безопасная диагностика установки: не печатает секреты и не подключается к Telegram."""
import importlib.util
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

REQUIRED = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_SESSION_STRING",
    "TELEGRAM_OWNER_ID",
    "TELEGRAM_GROUP_ID",
)
INTEGER_FIELDS = ("TELEGRAM_API_ID", "TELEGRAM_OWNER_ID", "TELEGRAM_GROUP_ID")


def check_environment(environ=None):
    source = os.environ if environ is None else environ
    problems = []
    for key in REQUIRED:
        if not source.get(key, "").strip():
            problems.append(f"Не задана переменная {key}")
    for key in INTEGER_FIELDS:
        raw = source.get(key, "").strip()
        if raw:
            try:
                if int(raw) <= 0:
                    problems.append(f"{key} должна быть положительным числом")
            except ValueError:
                problems.append(f"{key} должна быть целым числом")
    return problems


def check_dependencies(finder=None):
    finder = importlib.util.find_spec if finder is None else finder
    problems = []
    for module in ("telethon", "aiohttp"):
        if finder(module) is None:
            problems.append(
                f"Не установлен {module}: python -m pip install -r requirements.txt"
            )
    return problems


def check_database():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE check_table (value INTEGER)")
        connection.execute("INSERT INTO check_table VALUES (1)")
        if connection.execute("SELECT value FROM check_table").fetchone()[0] != 1:
            return ["SQLite не сохраняет записи"]
        return []
    finally:
        connection.close()


def check_ollama(url=None, model=None, opener=None):
    base = (url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
    selected = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    request = urllib.request.Request(base + "/api/tags", method="GET")
    opener = opener or urllib.request.urlopen
    try:
        with opener(request, timeout=3) as response:
            tags = json.load(response)
        names = [item.get("name", "") for item in tags.get("models", [])]
        if selected not in names and not any(
            name.startswith(selected + ":") for name in names
        ):
            return [f"Ollama доступна, но модель {selected} не найдена. Выполни: ollama pull {selected}"]
        return []
    except (OSError, ValueError, urllib.error.URLError):
        return ["Ollama недоступна. Запусти Ollama локально и проверь OLLAMA_URL."]


def run_diagnostics(environ=None, check_ai=True):
    checks = {
        "Конфигурация": check_environment(environ),
        "Зависимости": check_dependencies(),
        "SQLite": check_database(),
    }
    if check_ai:
        source = os.environ if environ is None else environ
        checks["Ollama"] = check_ollama(
            source.get("OLLAMA_URL"), source.get("OLLAMA_MODEL")
        )
    return checks


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(arg not in ("--offline",) for arg in argv):
        print("Использование: python doctor.py [--offline]")
        return 2
    print("Sherlock AI — диагностика (значения секретов скрыты)")
    checks = run_diagnostics(check_ai="--offline" not in argv)
    for name, errors in checks.items():
        print(f"{'✅' if not errors else '❌'} {name}")
        for issue in errors:
            print("  • " + issue)
    if all(not issues for issues in checks.values()):
        print("Локальные проверки пройдены. Авторизация Telegram не проверялась.")
        return 0
    print("Исправь перечисленные проблемы и повтори диагностику.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
