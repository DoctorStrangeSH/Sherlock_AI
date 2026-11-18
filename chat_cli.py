"""Текстовый локальный чат Sherlock AI — без Telegram и платного API."""
import asyncio

from local_ai import ask_local_ai

MAX_CONTEXT = 12


async def chat(reader=input, writer=print):
    writer("Sherlock AI ❤️  Локальный режим. /clear — очистить контекст, /exit — выход.")
    history = []
    while True:
        try:
            question = reader("Шерлок > ").strip()
        except (EOFError, KeyboardInterrupt):
            writer("\nДо встречи!")
            return
        if question.lower() in ("/exit", "/quit"):
            writer("До встречи!")
            return
        if question.lower() == "/clear":
            history.clear()
            writer("🧹 Контекст этой сессии очищен.")
            continue
        if not question:
            continue
        answer = await ask_local_ai(question, history)
        writer("Sherlock AI > " + answer)
        if answer.startswith("Локальная модель недоступна.") or answer.startswith("Слишком длинный запрос"):
            continue
        history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])
        history = history[-MAX_CONTEXT:]


if __name__ == "__main__":
    asyncio.run(chat())
