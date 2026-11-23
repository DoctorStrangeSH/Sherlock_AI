"""Offline end-to-end simulation of the Telegram draft approval logic.

No Telegram client, session, internet, Ollama or real sending is used.
"""

from contact_style import DEFAULT_STYLE
from conversation_context import RecentChatContext
from draft_queue import DraftQueue
from reply_drafts import can_prepare_draft, draft_question


def run_simulation():
    owner_id = 100
    contact_id = 200
    allowed_ids = {contact_id}
    context = RecentChatContext()
    drafts = DraftQueue()

    context.add(contact_id, "owner", "Сегодня занят, завтра могу созвониться.")
    context.add(300, "owner", "Это сообщение другого контакта — оно приватное.")
    incoming = "Привет! Тогда завтра во сколько?"
    approved = can_prepare_draft(
        enabled=True,
        private=True,
        outgoing=False,
        sender_id=contact_id,
        owner_id=owner_id,
        allowed_ids=allowed_ids,
        text=incoming,
    )
    assert approved, "Allowed incoming message should be eligible"
    prompt = draft_question(incoming, "Анна", context.recent(contact_id), DEFAULT_STYLE)
    assert "Сегодня занят" in prompt
    assert "другого контакта" not in prompt

    # Fake model reply: deterministic and contains no actual LLM call.
    simulated_model_response = "Привет! Давай завтра в семь, если тебе удобно."
    draft = drafts.add(contact_id, "Анна", simulated_model_response)
    assert drafts.take_for_send(draft.draft_id, enabled=False, allowed_ids=allowed_ids) is None
    edited = drafts.edit(
        draft.draft_id, "Привет! Давай завтра около семи?",
        enabled=True, allowed_ids=allowed_ids,
    )
    assert edited and edited.reply != simulated_model_response

    # Explicit approval consumes the draft. No external message is sent here.
    confirmed = drafts.take_for_send(
        draft.draft_id, enabled=True, allowed_ids=allowed_ids
    )
    assert confirmed is not None
    assert confirmed.recipient_id == contact_id
    assert confirmed.reply == "Привет! Давай завтра около семи?"
    assert drafts.take_for_send(
        draft.draft_id, enabled=True, allowed_ids=allowed_ids
    ) is None
    return confirmed


def main():
    result = run_simulation()
    print("✅ Сценарий входящего сообщения: успешно")
    print("✅ Изоляция контекста по контактам: успешно")
    print("✅ Запрет отправки без включения: успешно")
    print("✅ Редактирование и одноразовое подтверждение: успешно")
    print(f"Тестовый адресат: {result.recipient_name} (вымышленный)")
    print(f"Тестовый текст: {result.reply}")
    print("🔒 Реальная отправка в Telegram НЕ выполнялась.")
    print("🔒 Ollama и Telegram-ключи для этой проверки НЕ нужны.")


if __name__ == "__main__":
    main()
