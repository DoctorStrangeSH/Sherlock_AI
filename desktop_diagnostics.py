"""Privacy-conscious local diagnostics for Sherlock AI desktop."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
from pathlib import Path
import re
import sys
import threading
from datetime import datetime, timezone

APP_VERSION = "1.0.0-dev"
LOG_FILENAME = "sherlock.log"
MAX_LOG_BYTES = 512 * 1024
LOG_BACKUP_COUNT = 3
REPORT_LOG_LINES = 120

_SECRET_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"\b\d{5,}:[A-Za-z0-9_-]{20,}\b"), "[REDACTED_BOT_TOKEN]"),
    (re.compile(r"(?i)\b(api[_-]?key|api[_-]?hash|access[_-]?token|refresh[_-]?token|password|passwd|secret|authorization)\b(\s*[:=]\s*)(['\"]?)[^\s,'\";]+"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)([?&](?:token|key|hash|auth|password)=)[^&#\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)([A-Z]:\\Users\\)[^\\\s]+"), r"\1[USER]"),
    (re.compile(r"(?i)(/home/)[^/\s]+"), r"\1[USER]"),
)


def redact_sensitive_text(value: object) -> str:
    result = str(value)
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def safe_exception_summary(error: BaseException) -> str:
    # OSError messages frequently embed full user-selected paths and filenames.
    message = "OS operation failed" if isinstance(error, OSError) else redact_sensitive_text(str(error)).strip()
    if len(message) > 500:
        message = message[:497] + "..."
    return f"{type(error).__name__}: {message or 'no details'}"


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))


def diagnostics_directory(data_dir: str | Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir).expanduser() / "logs"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".sherlock_ai"))
    else:
        base = Path.home() / ".sherlock_ai"
    return base / "SherlockAI" / "logs"


def configure_diagnostics(data_dir: str | Path | None = None, *, app_version: str = APP_VERSION):
    logger = logging.getLogger("sherlock_ai")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    directory = diagnostics_directory(data_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Diagnostics must never prevent the assistant from starting.
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        return logger, None
    log_path = directory / LOG_FILENAME
    for handler in tuple(logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            if Path(handler.baseFilename) == log_path.resolve():
                return logger, log_path
            logger.removeHandler(handler)
            handler.close()
    try:
        handler = RotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8", delay=True,
        )
    except OSError:
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        return logger, None
    handler.setFormatter(_RedactingFormatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.info("Diagnostics initialized · version=%s", redact_sensitive_text(app_version))
    return logger, log_path


def install_exception_hooks(logger: logging.Logger | None = None) -> None:
    target = logger or logging.getLogger("sherlock_ai")

    def main_exception_hook(exc_type, exc_value, traceback_obj) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, traceback_obj)
            return
        target.error("Uncaught application exception · %s", safe_exception_summary(exc_value))

    sys.excepthook = main_exception_hook
    if hasattr(threading, "excepthook"):
        def thread_exception_hook(args) -> None:
            target.error(
                "Uncaught worker exception · thread=%s · %s",
                redact_sensitive_text(args.thread.name if args.thread else "unknown"),
                safe_exception_summary(args.exc_value),
            )
        threading.excepthook = thread_exception_hook


def write_support_report(destination: str | Path, log_path: str | Path, *, app_version: str = APP_VERSION) -> Path:
    source = Path(log_path)
    lines: list[str] = []
    if source.is_file():
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = ["Log file could not be read."]
    report = {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": {"name": "Sherlock AI", "version": redact_sensitive_text(app_version)},
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "privacy": {
            "chat_history_included": False,
            "prompts_and_model_output_included": False,
            "file_contents_included": False,
            "credentials_redacted": True,
        },
        "recent_logs": [redact_sensitive_text(line) for line in lines[-REPORT_LOG_LINES:]],
    }
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
