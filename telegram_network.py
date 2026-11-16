"""Shared, secret-safe Telegram network options."""
import os

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}


def parse_env_bool(value, *, default=False):
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError("TELEGRAM_USE_IPV6 must be true or false")


def telegram_client_options(environ=None):
    """Options shared by onboarding, read-only checks, and the assistant."""
    env = os.environ if environ is None else environ
    ipv6 = parse_env_bool(env.get("TELEGRAM_USE_IPV6"), default=False)
    options = {"use_ipv6": ipv6, "timeout": 20, "connection_retries": 3, "retry_delay": 2}
    proxy_type = str(env.get("TELEGRAM_PROXY_TYPE", "none")).strip().lower()
    if proxy_type in ("", "none"):
        return options
    if proxy_type != "mtproto":
        raise ValueError("Неподдерживаемый TELEGRAM_PROXY_TYPE; выбери none или mtproto")
    host = str(env.get("TELEGRAM_PROXY_HOST", "")).strip()
    secret = str(env.get("TELEGRAM_PROXY_SECRET", "")).strip()
    raw_port = str(env.get("TELEGRAM_PROXY_PORT", "")).strip()
    if not host or any(ch.isspace() for ch in host) or not secret:
        raise ValueError("Для MTProto требуются адрес сервера и секрет")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("Порт MTProto должен быть числом") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Порт MTProto должен быть между 1 и 65535")
    # Lazy import: offline diagnostics can run without Telethon installed.
    from telethon import connection

    # Randomized intermediate is intended for dd-prefixed secrets. For a
    # conventional hex secret, use regular intermediate framing instead.
    # A wrong packet codec can result in negative packet-length errors.
    transport = (connection.ConnectionTcpMTProxyRandomizedIntermediate
                 if secret.lower().startswith("dd")
                 else connection.ConnectionTcpMTProxyIntermediate)
    options.update({
        "use_ipv6": False,
        "connection": transport,
        "proxy": (host, port, secret),
    })
    return options
