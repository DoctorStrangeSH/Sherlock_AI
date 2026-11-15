"""Shared, secret-safe Telegram network options."""
import os


_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}


def parse_env_bool(value, *, default=False):
    """Parse a boolean environment value without silently accepting typos."""
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError("TELEGRAM_USE_IPV6 must be true or false")


def telegram_client_options(environ=None):
    """Options shared by setup, read-only checks and the running assistant."""
    env = os.environ if environ is None else environ
    return {
        "use_ipv6": parse_env_bool(env.get("TELEGRAM_USE_IPV6"), default=False),
        "timeout": 20,
        "connection_retries": 3,
        "retry_delay": 2,
    }
