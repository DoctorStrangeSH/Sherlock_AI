"""Small, UI-independent conversation state for desktop Sherlock AI."""

from dataclasses import dataclass, field

MAX_CONTEXT = 12
ERROR_PREFIXES = (
    "Локальная модель недоступна.",
    "Слишком длинный запрос",
    "Напиши вопрос после .ask",
    "Модель вернула пустой ответ.",
)


@dataclass
class ConversationSession:
    history: list[dict[str, str]] = field(default_factory=list)

    def clear(self) -> None:
        self.history.clear()

    def snapshot(self) -> list[dict[str, str]]:
        return [dict(item) for item in self.history]

    def record(self, question: str, answer: str) -> bool:
        """Only successful turns enter the context sent to the model."""
        if not question.strip() or not answer.strip() or answer.startswith(ERROR_PREFIXES):
            return False
        self.history.extend((
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ))
        self.history = self.history[-MAX_CONTEXT:]
        return True
