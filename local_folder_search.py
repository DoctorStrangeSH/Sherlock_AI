"""Bounded, read-only search within an explicitly selected folder."""
from pathlib import Path
from local_file_preview import TEXT_SUFFIXES

MAX_FILES = 250
MAX_RESULTS = 30
MAX_DEPTH = 3
MAX_READ_BYTES = 128 * 1024
MAX_QUERY_LENGTH = 120


def search_text_folder(folder, query):
    """Search filenames and bounded text content; never follow directory symlinks."""
    root = Path(folder).expanduser()
    needle = str(query).strip().casefold()
    if not needle or len(needle) > MAX_QUERY_LENGTH:
        raise ValueError("Поисковый запрос должен содержать от 1 до 120 символов.")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Выбери существующую папку (не ссылку).")
    checked = 0
    matches = []
    skipped = 0
    pending = [(root, 0)]
    while pending and checked < MAX_FILES and len(matches) < MAX_RESULTS:
        current, depth = pending.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            skipped += 1
            continue
        for entry in entries:
            if checked >= MAX_FILES or len(matches) >= MAX_RESULTS:
                break
            try:
                if entry.is_symlink() or entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    if depth < MAX_DEPTH:
                        pending.append((entry, depth + 1))
                    continue
                if not entry.is_file() or entry.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                checked += 1
                if entry.stat().st_size > MAX_READ_BYTES:
                    skipped += 1
                    continue
                if needle in entry.name.casefold():
                    matches.append({"path": str(entry), "excerpt": "Совпадение в названии файла"})
                    continue
                with entry.open("rb") as stream:
                    raw = stream.read(MAX_READ_BYTES + 1)
                if b"\x00" in raw or len(raw) > MAX_READ_BYTES:
                    skipped += 1
                    continue
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    content = raw.decode("cp1251", errors="replace")
                index = content.casefold().find(needle)
                if index >= 0:
                    matches.append({"path": str(entry), "excerpt": content[max(0, index - 55):index + len(needle) + 75].replace("\n", " ").replace("\r", " ")})
            except (OSError, ValueError):
                skipped += 1
    return {"matches": matches, "checked": checked, "skipped": skipped,
            "limit_reached": checked >= MAX_FILES or len(matches) >= MAX_RESULTS}
