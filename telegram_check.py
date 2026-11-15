"""Read-only Telegram connectivity check: sends no messages, saves no session."""
import asyncio
import os


async def check():
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session = os.environ["TELEGRAM_SESSION_STRING"]
    expected = int(os.environ["TELEGRAM_OWNER_ID"])
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        if not await client.is_user_authorized():
            print("❌ Telegram-сессия недействительна. Создай новую через telegram_setup.py.")
            return 1
        me = await client.get_me()
        if me is None or me.id != expected:
            print("❌ OWNER_ID не совпадает с авторизованным аккаунтом. Не запускай секретаря.")
            return 1
        print("✅ Telegram подключён. Аккаунт подтверждён, сообщения никому не отправлены.")
        return 0


def main():
    try:
        return asyncio.run(check())
    except (KeyboardInterrupt, SystemExit):
        print("Проверка прервана.")
        return 130
    except Exception:
        print("❌ Не удалось подключиться. Проверь сеть, сессию и конфигурацию.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
