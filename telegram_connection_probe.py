"""Read-only MTProto transport probe; never sends login codes or saves a session."""

import asyncio
import logging

from telegram_setup import ask_network_settings
from telegram_network import telegram_client_options


async def probe(options, *, timeout_seconds=30):
    """Perform only the MTProto key exchange, without account authentication."""
    from telethon import TelegramClient
    from telethon.sessions import MemorySession

    # connect() performs MTProto key negotiation, but not a user login.
    # No API requests are made. The temporary auth key is held in memory only.
    client = TelegramClient(MemorySession(), 1, "0" * 32, **options)
    try:
        await asyncio.wait_for(client.connect(), timeout_seconds)
        return bool(client.is_connected())
    finally:
        await client.disconnect()


def main():
    print("SHERLOCK AI — ПРОВЕРКА MTProto")
    print("Номер телефона, Telegram-код и API-ключи НЕ нужны.")
    print("Никаких сообщений не отправляем. Сессию не сохраняем.")
    try:
        network = ask_network_settings()
        # Telethon may produce a full background-task traceback containing
        # transport internals; the user-facing result is intentionally concise.
        logging.getLogger("telethon.network").setLevel(logging.CRITICAL)
        logging.getLogger("telethon.client").setLevel(logging.CRITICAL)
        options = telegram_client_options(network)
        print("Проверяем MTProto-соединение (максимум 30 секунд)...")
        connected = asyncio.run(probe(options))
    except KeyboardInterrupt:
        print("Проверка отменена.")
        return 130
    except asyncio.TimeoutError:
        print("❌ MTProto: превышено время ожидания (30 секунд).")
        return 1
    except (ValueError, OSError, ConnectionError, RuntimeError) as exc:
        # Never print the exception text: proxy libraries can include secrets.
        print(f"❌ MTProto: соединение не установлено ({type(exc).__name__}).")
        return 1
    except Exception as exc:
        print(f"❌ MTProto: ошибка проверки ({type(exc).__name__}).")
        return 1

    if connected:
        print("✅ MTProto: транспортное соединение установлено.")
        print("Это НЕ означает, что личный аккаунт авторизован или код доставлен.")
        return 0
    print("❌ MTProto: клиент не подтвердил соединение.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
