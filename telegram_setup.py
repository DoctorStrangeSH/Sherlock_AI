"""Interactive local-only personal Telegram authorization. No sessions uploaded."""
import asyncio
from getpass import getpass
import os
from pathlib import Path

from telegram_network import telegram_client_options

ENV_PATH = Path(__file__).resolve().parent / ".env"


def env_value(value):
    if any(ch in value for ch in ("\r", "\n", "\0")):
        raise ValueError("Недопустимые символы в настройке")
    return value


def save_local_config(values, destination=ENV_PATH):
    lines = "".join(f"{key}={env_value(str(value))}\n" for key, value in values.items())
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(lines)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def delivery_hint(sent):
    """Only show the delivery channel, never the raw server response or code hash."""
    kind = type(getattr(sent, "type", None)).__name__
    descriptions = {
        "SentCodeTypeApp": "служебный чат Telegram на уже подключённых устройствах",
        "SentCodeTypeSms": "SMS на номер аккаунта",
        "SentCodeTypeCall": "телефонный звонок",
        "SentCodeTypeFlashCall": "входящий проверочный звонок",
        "SentCodeTypeMissedCall": "пропущенный звонок",
        "SentCodeTypeEmailCode": "электронная почта, привязанная к входу Telegram",
        "SentCodeTypeFragmentSms": "Fragment (см. инструкции Telegram)",
        "SentCodeTypeFirebaseSms": "проверка через официальное мобильное приложение",
        "SentCodeTypeSetUpEmailRequired": "сначала требуется настройка почты в официальном Telegram",
    }
    return descriptions.get(kind, "способ не определён текущей версией программы")


def next_delivery_hint(sent):
    """Describe Telegram's next permitted delivery method without exposing hashes."""
    kind = type(getattr(sent, "next_type", None)).__name__
    descriptions = {
        "CodeTypeApp": "служебное уведомление Telegram",
        "CodeTypeSms": "SMS",
        "CodeTypeCall": "телефонный звонок",
        "CodeTypeFlashCall": "короткий входящий звонок",
        "CodeTypeMissedCall": "пропущенный звонок",
        "CodeTypeFragmentSms": "Fragment",
        "CodeTypeEmailCode": "электронная почта",
    }
    return descriptions.get(kind, "Telegram не сообщил альтернативный способ")


def delivery_timeout(sent):
    value = getattr(sent, "timeout", None)
    return value if type(value) is int and value >= 0 else None


async def request_alternative_code(client, phone, sent):
    """Ask Telegram for its advertised next code method, only after user consent."""
    if not getattr(sent, "next_type", None):
        raise RuntimeError("Telegram не предоставил альтернативный способ доставки")
    phone_hash = getattr(sent, "phone_code_hash", None)
    if not phone_hash:
        raise RuntimeError("Telegram не предоставил идентификатор запроса кода")
    from telethon.tl.functions.auth import ResendCodeRequest
    return await client(ResendCodeRequest(phone, phone_hash))


def authorization_error_message(exc):
    """Return useful advice without ever including exception text or credentials."""
    kind = type(exc).__name__
    if kind == "PhoneCodeInvalidError":
        return "❌ Код не подходит к текущему запросу. Старые коды Desktop/Web не используй."
    if kind == "PhoneCodeExpiredError":
        return "❌ Срок действия кода истёк. Не запрашивай новый код многократно подряд."
    if kind in {"PhoneCodeEmptyError", "PhoneCodeHashEmptyError", "PhoneCodeHashInvalidError"}:
        return "❌ Запрос кода недействителен. Следующую попытку делай позже."
    if kind in {"SessionPasswordNeededError", "PasswordHashInvalidError"}:
        return "❌ Требуется корректный пароль двухэтапной проверки Telegram."
    if kind in {"FloodWaitError", "PhoneNumberFloodError", "PhonePasswordFloodError"}:
        seconds = getattr(exc, "seconds", None)
        wait = f" Подожди не менее {int(seconds)} секунд." if type(seconds) is int and 0 < seconds < 864000 else ""
        return "❌ Telegram ограничил число попыток авторизации." + wait
    if kind in {"IncompleteReadError", "ConnectionError", "ConnectionResetError", "TimeoutError",
                "ServerClosedConnectionError", "InvalidBufferError"} or isinstance(exc, (ConnectionError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError)):
        return "❌ Соединение разорвалось во время авторизации. Это не подтверждает ошибку кода."
    if kind in {"ApiIdInvalidError", "ApiIdPublishedFloodError"}:
        return "❌ Telegram отклонил API ID приложения. Проверь личные ключи на my.telegram.org."
    return f"❌ Ошибка авторизации ({kind}). Секретные данные не выводятся."


def ask_network_settings():
    print("Подключение: 1 — MTProto-прокси, 2 — напрямую через IPv6, 3 — напрямую через IPv4")
    choice = input("Выбери способ подключения [1]: ").strip() or "1"
    if choice not in {"1", "2", "3"}:
        raise ValueError("Выбери 1, 2 или 3")
    values = {"TELEGRAM_PROXY_TYPE": "none", "TELEGRAM_USE_IPV6": str(choice == "2").lower()}
    if choice == "1":
        print("Введи параметры проверенного MTProto-прокси. Секрет вводится скрыто.")
        values.update({
            "TELEGRAM_PROXY_TYPE": "mtproto",
            "TELEGRAM_PROXY_HOST": input("Адрес MTProto (hostname): ").strip(),
            "TELEGRAM_PROXY_PORT": input("Порт MTProto [443]: ").strip() or "443",
            "TELEGRAM_PROXY_SECRET": getpass("Секрет MTProto (ввод скрыт): ").strip(),
        })
    telegram_client_options(values)  # Validate before contacting Telegram.
    return values


async def authorize():
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    print("ВНИМАНИЕ: отзови только старую скомпрометированную сессию; не выходи из Web/Desktop.")
    if input("Старая сессия отозвана? Напиши ДА: ").strip() != "ДА":
        print("Настройка остановлена.")
        return 1
    if ENV_PATH.exists():
        print("Файл .env уже существует. Ничего не перезаписано.")
        return 1
    try:
        api_id = int(input("Telegram API ID: ").strip())
        api_hash = getpass("Telegram API hash (ввод скрыт): ").strip()
        if api_id <= 0 or len(api_hash) != 32 or any(ch not in "0123456789abcdefABCDEF" for ch in api_hash):
            raise ValueError("Некорректные API ID или hash")
        network = ask_network_settings()
    except ValueError as exc:
        print(f"Некорректная настройка: {exc}")
        return 1

    print("Создаём отдельную локальную сессию личного аккаунта. Коды и секреты не публикуются.")
    # IMPORTANT: `async with TelegramClient(...)` implicitly calls start(),
    # which triggers Telethon's own login prompt before our delivery diagnostics.
    # Explicit connect() performs only the transport handshake.
    client = TelegramClient(StringSession(), api_id, api_hash, **telegram_client_options(network))
    await client.connect()
    try:
        phone = input("Номер телефона (+...): ").strip()
        if not phone.startswith("+") or not phone[1:].isdigit():
            print("Номер должен быть в международном формате, например +7...")
            return 1
        print("Запрашиваем код у Telegram...")
        sent = await client.send_code_request(phone)
        print("Telegram указал способ доставки:", delivery_hint(sent))
        timeout = delivery_timeout(sent)
        if timeout is not None:
            print(f"Время ожидания перед альтернативным способом: {timeout} сек.")
        next_hint = next_delivery_hint(sent)
        if next_hint != "Telegram не сообщил альтернативный способ":
            print("Следующий способ, разрешённый Telegram:", next_hint)
        print("Проверь служебный чат Telegram (отправитель 777000) на остальных активных устройствах.")
        if getattr(sent, "next_type", None):
            answer = input("Если код не пришёл и время ожидания прошло, запросить следующий способ? [д/н]: ").strip().lower()
            if answer in {"д", "да", "y", "yes"}:
                sent = await request_alternative_code(client, phone, sent)
                print("Новый способ доставки:", delivery_hint(sent))
                timeout = delivery_timeout(sent)
                if timeout is not None:
                    print(f"Время ожидания: {timeout} сек.")
            else:
                print("Альтернативный запрос не выполнялся.")
        code = getpass("Код из Telegram (ввод скрыт): ").strip()
        if not code:
            print("Код не введён, настройка остановлена.")
            return 1
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass("Пароль двухфакторной защиты (ввод скрыт): "))
        me = await client.get_me()
        if me is None or getattr(me, "bot", False):
            print("Не удалось подтвердить личный аккаунт.")
            return 1
        session = client.session.save()
        print(f"Авторизация успешна: аккаунт ID {me.id}.")
        raw_group = input("ID группы с темами (можно оставить пустым): ").strip()
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
            "TELEGRAM_OWNER_ID": me.id,
            "TELEGRAM_GROUP_ID": group_id,
            **network,
            "OLLAMA_MODEL": "auto",
        }
        try:
            save_local_config(values)
        except FileExistsError:
            print(".env уже создан другим процессом. Ничего не перезаписано.")
            return 1
    finally:
        await client.disconnect()
    print("✅ Секреты сохранены только в локальном .env (в .gitignore).")
    print("Не пересылай .env. Проверка: python run_local.py telegram_check.py")
    if not group_id:
        print("⚠️ Перед запуском secretary.py впиши TELEGRAM_GROUP_ID в .env.")
    return 0


def main():
    try:
        return asyncio.run(authorize())
    except KeyboardInterrupt:
        print("\nНастройка отменена. Секреты не сохранены.")
        return 130
    except Exception as exc:
        print(authorization_error_message(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
