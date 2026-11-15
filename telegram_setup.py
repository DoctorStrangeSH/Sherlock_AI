"""Interactive local-only Telegram onboarding. Never prints or uploads a StringSession."""
import asyncio
from getpass import getpass
import os
from pathlib import Path

from telegram_network import telegram_client_options

ENV_PATH = Path(__file__).resolve().parent / ".env"


def env_value(value):
    """Quote values safely for our simple KEY=VALUE local configuration format."""
    if any(ch in value for ch in ("\r", "\n", "\0")):
        raise ValueError("Недопустимые символы в настройке")
    return value


def save_local_config(values, destination=ENV_PATH):
    """Create a new private configuration, never overwrite an existing one."""
    lines = "".join(f"{key}={env_value(str(value))}\n" for key, value in values.items())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(destination), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(lines)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


async def authorize():
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    print("ВНИМАНИЕ: сначала отзови старую скомпрометированную сессию в Telegram → Устройства.")
    confirmation = input("Старая сессия отозвана? Напиши ДА: ").strip()
    if confirmation != "ДА":
        print("Настройка остановлена. Сначала отзови старую сессию.")
        return 1
    if ENV_PATH.exists():
        print("Файл .env уже существует. Ничего не перезаписано.")
        return 1

    try:
        api_id = int(input("Telegram API ID: ").strip())
        api_hash = getpass("Telegram API hash (ввод скрыт): ").strip()
        if api_id <= 0 or len(api_hash) != 32 or any(ch not in "0123456789abcdefABCDEF" for ch in api_hash):
            raise ValueError("Некорректные API ID или hash")
    except ValueError:
        print("Неверный API ID/hash. Проверь my.telegram.org.")
        return 1

    print("Авторизация создаст НОВУЮ Telegram-сессию только на твоём компьютере.")
    raw_ipv6 = input("Использовать IPv6 для Telegram? [Y/n]: ").strip().lower()
    use_ipv6 = raw_ipv6 not in {"n", "no", "нет", "false", "0"}
    network_options = telegram_client_options({"TELEGRAM_USE_IPV6": str(use_ipv6).lower()})
    print("Сетевой режим: IPv6." if use_ipv6 else "Сетевой режим: IPv4.")
    async with TelegramClient(StringSession(), api_id, api_hash, **network_options) as client:
        await client.start(
            phone=lambda: input("Номер телефона (+...): ").strip(),
            code_callback=lambda: input("Код из Telegram: ").strip(),
            password=lambda: getpass("Пароль двухфакторной защиты (если нужен): "),
        )
        me = await client.get_me()
        if me is None or getattr(me, "bot", False):
            print("Не удалось подтвердить личный аккаунт.")
            return 1
        session = client.session.save()
        owner_id = me.id
        print(f"Авторизация успешна: аккаунт ID {owner_id}.")
        raw_group = input("ID твоей группы с темами (можно оставить пустым до настройки): ").strip()
        try:
            group_id = int(raw_group) if raw_group else 0
            if group_id > 0:
                raise ValueError("ID группы Telegram обычно отрицательный")
        except ValueError:
            print("ID группы должен быть отрицательным числом. Файл не создан.")
            return 1

        values = {
            "TELEGRAM_API_ID": api_id,
            "TELEGRAM_API_HASH": api_hash,
            "TELEGRAM_SESSION_STRING": session,
            "TELEGRAM_OWNER_ID": owner_id,
            "TELEGRAM_GROUP_ID": group_id,
            "TELEGRAM_USE_IPV6": str(use_ipv6).lower(),
            "OLLAMA_MODEL": "auto",
        }
        try:
            save_local_config(values)
        except FileExistsError:
            print(".env уже создан другим процессом. Ничего не перезаписано.")
            return 1
    print("✅ Секреты сохранены только в локальном .env (в .gitignore).")
    print("Не пересылай файл .env. Для проверки: python run_local.py doctor.py --offline")
    if not group_id:
        print("⚠️ Перед запуском secretary.py впиши TELEGRAM_GROUP_ID в .env.")
    return 0


def main():
    try:
        return asyncio.run(authorize())
    except KeyboardInterrupt:
        print("\nНастройка отменена. Секреты не сохранены.")
        return 130
    except Exception:
        # Telethon exceptions may contain sensitive data. Do not print exception details.
        print("❌ Не удалось авторизоваться. Проверь сеть, API-ключи и Telegram.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
