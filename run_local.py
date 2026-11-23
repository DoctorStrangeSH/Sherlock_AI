"""Launch a project script with secrets from local gitignored .env."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ALLOWED_SCRIPTS = {"doctor.py", "secretary.py", "telegram_check.py"}
ALLOWED_KEYS = {
    "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING",
    "TELEGRAM_OWNER_ID", "TELEGRAM_GROUP_ID", "TELEGRAM_USE_IPV6",
    "TELEGRAM_PROXY_TYPE", "TELEGRAM_PROXY_HOST", "TELEGRAM_PROXY_PORT",
    "TELEGRAM_PROXY_SECRET", "TOPIC_INCOMING",
    "TOPIC_REMINDERS", "TOPIC_STATS", "TOPIC_IMPORTANT",
    "FILTER_MODE", "OLLAMA_MODEL", "OLLAMA_URL",
}


def load_local_environment(path=ROOT / ".env", inherited=None):
    result = dict(os.environ if inherited is None else inherited)
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator != "=" or name.strip() not in ALLOWED_KEYS:
            raise ValueError("Некорректный или неизвестный параметр в .env")
        if any(ch in value for ch in ("\r", "\0")):
            raise ValueError("Недопустимый символ в .env")
        result[name.strip()] = value.strip()
    return result


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ALLOWED_SCRIPTS:
        print("Использование: python run_local.py doctor.py [--offline] / telegram_check.py / secretary.py")
        return 2
    try:
        env = load_local_environment()
    except (OSError, ValueError):
        print("Нет корректного локального .env. Запусти: python telegram_setup.py")
        return 1
    return subprocess.call([sys.executable, str(ROOT / args[0]), *args[1:]], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
