"""Select an already installed Ollama model without cloud downloads."""

PREFERRED_MODELS = ("qwen3:8b", "qwen3.5:9b", "qwen3:4b", "qwen2.5:3b")


def choose_model(names, requested=None):
    """Explicit selection wins; otherwise prefer known local models."""
    installed = [name for name in names if isinstance(name, str) and name]
    if requested and requested.lower() != "auto":
        if requested in installed:
            return requested
        raise ValueError(
            f"Модель {requested} не скачана. Выполни: ollama pull {requested}"
        )
    for preferred in PREFERRED_MODELS:
        if preferred in installed:
            return preferred
    if installed:
        return installed[0]
    raise ValueError(
        "Нет установленных моделей. Для начала: ollama pull qwen3:8b"
    )
