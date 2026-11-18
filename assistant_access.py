"""Telegram guardrails for commands handling private assistant data."""

def is_saved_messages_owner(event, owner_id):
    return bool(
        event.out
        and event.is_private
        and event.sender_id == owner_id
        and event.chat_id == owner_id
    )
