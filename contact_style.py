"""Owner-configured reply styles, kept separate from model-provided text."""

STYLES = {
    "warm": "Пиши тепло, естественно и дружелюбно, без фамильярности.",
    "concise": "Пиши коротко, по существу, без лишних эмодзи.",
    "professional": "Пиши вежливо, сдержанно и профессионально.",
}
DEFAULT_STYLE = "warm"


def setting_key(contact_id: int) -> str:
    if not isinstance(contact_id, int) or contact_id <= 0:
        raise ValueError("Неверный ID контакта")
    return f"draft_contact_style_{contact_id}"


def validated_style(style: str) -> str:
    if style not in STYLES:
        raise ValueError("Доступны стили: warm / concise / professional")
    return style


def style_instruction(style: str) -> str:
    return STYLES[validated_style(style)]
