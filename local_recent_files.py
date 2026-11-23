"""Read-only inventory of recently changed text files in a selected directory."""
from datetime import datetime
from pathlib import Path

from local_file_preview import TEXT_SUFFIXES

MAX_SCANNED = 500
MAX_DEPTH = 3
MAX_RECENT = 25


def recent_text_files(folder, cancel_event=None):
    root = Path(folder).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Выбери существующую папку (не ссылку).")
    pending = [(root, 0)]
    scanned = 0
    skipped = 0
    items = []
    while pending and scanned < MAX_SCANNED:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Recent-files scan cancelled.")
        current, depth = pending.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda entry: entry.name.casefold())
        except OSError:
            skipped += 1
            continue
        for entry in entries:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Recent-files scan cancelled.")
            if scanned >= MAX_SCANNED:
                break
            try:
                if entry.name.startswith(".") or entry.is_symlink():
                    continue
                if entry.is_dir():
                    if depth < MAX_DEPTH:
                        pending.append((entry, depth + 1))
                    continue
                if not entry.is_file() or entry.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                scanned += 1
                info = entry.stat()
                items.append({"path": str(entry), "modified": info.st_mtime,
                              "size": info.st_size})
            except OSError:
                skipped += 1
    items.sort(key=lambda item: (-item["modified"], item["path"].casefold()))
    return {"files": items[:MAX_RECENT], "checked": scanned,
            "skipped": skipped, "limit_reached": scanned >= MAX_SCANNED}


def format_recent_file(item):
    when = datetime.fromtimestamp(item["modified"]).strftime("%d.%m.%Y %H:%M")
    return "{} · {} байт\n{}".format(when, item["size"], item["path"])
