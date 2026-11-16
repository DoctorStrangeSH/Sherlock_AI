"""Read-only, bounded local text preview.

Only explicitly selected local files are opened. No network calls or mutations.
"""
from pathlib import Path

MAX_PREVIEW_BYTES = 65536
MAX_FILE_BYTES = 2 * 1024 * 1024
TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv", ".tsv", ".log", ".py", ".yaml", ".yml", ".ini", ".toml"}


def preview_text_file(path):
    file_path = Path(path).expanduser()
    if file_path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError("Предпросмотр этого типа файла пока не поддерживается.")
    if not file_path.is_file():
        raise ValueError("Выбранный файл не найден.")
    size = file_path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("Файл слишком большой для предпросмотра (максимум 2 МБ).")
    with file_path.open("rb") as stream:
        sample = stream.read(MAX_PREVIEW_BYTES + 1)
    if b"\x00" in sample:
        raise ValueError("Похоже, это двоичный файл.")
    truncated = len(sample) > MAX_PREVIEW_BYTES
    sample = sample[:MAX_PREVIEW_BYTES]
    try:
        content = sample.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = sample.decode("cp1251", errors="replace")
    return {
        "name": file_path.name,
        "size": size,
        "content": content,
        "truncated": truncated,
    }
