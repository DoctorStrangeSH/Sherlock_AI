# secretary.py
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import *
from database import db
from filters import smart_filter
from analytics import analytics
from security import security
from scheduler import Scheduler
from local_ai import ask_local_ai
from assistant_access import is_saved_messages_owner
from reply_drafts import can_prepare_draft, draft_question, display_draft
from draft_queue import DraftQueue
from conversation_context import RecentChatContext
from contact_style import setting_key, validated_style, DEFAULT_STYLE

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Состояние
is_online = False
current_mode = db.get_setting("current_mode", "normal")
FILTER_MODE = db.get_setting("filter_mode", FILTER_MODE)
is_online = db.get_setting("is_online", False)
ai_dialogue_lock = asyncio.Lock()
pending_reply_drafts = DraftQueue()
recent_chat_context = RecentChatContext()

def get_time():
    return datetime.now(MOSCOW_TZ)

def get_auto_reply(name):
    hour = get_time().hour
    
    mode_replies = {
        "normal": {
            "morning": f"☀️ Доброе утро, {name}! Sherlock скоро ответит.",
            "day": f"👨‍💻 Добрый день, {name}! Sherlock на связи.",
            "evening": f"🌆 Добрый вечер, {name}! Sherlock отошёл.",
            "night": f"🌙 Ночь! Sherlock спит. Не будить!",
        },
        "busy": {
            "morning": f"😤 {name}, Sherlock очень занят!",
            "day": f"😤 {name}, Sherlock на важном деле!",
            "evening": f"😤 {name}, Sherlock работает!",
            "night": f"😤 {name}, даже ночью занят!",
        },
        "sleeping": {
            "morning": f"😴 {name}, Sherlock ещё спит...",
            "day": f"😴 {name}, Sherlock спит.",
            "evening": f"😴 {name}, Sherlock уснул.",
            "night": f"😴 {name}, Sherlock крепко спит!",
        },
        "meeting": {
            "morning": f"🤝 {name}, Sherlock на встрече.",
            "day": f"🤝 {name}, Sherlock на встрече.",
            "evening": f"🤝 {name}, встреча затянулась...",
            "night": f"🤝 {name}, встреча...",
        },
    }
    
    if 5 <= hour < 12:
        time_key = "morning"
    elif 12 <= hour < 17:
        time_key = "day"
    elif 17 <= hour < 23:
        time_key = "evening"
    else:
        time_key = "night"
    
    return mode_replies[current_mode][time_key]

async def send_to_topic(topic_id, message):
    try:
        await client.send_message(GROUP_ID, message, reply_to=topic_id)
        logger.info(f"Отправлено в тему {topic_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# === КОМАНДЫ (без кнопок) ===

@client.on(events.NewMessage(outgoing=True, pattern=r'\.menu'))
async def show_menu(event):
    menu_text = """🎛 **МЕНЮ**

**Статусы:**
.online — включить онлайн
.offline — включить оффлайн
.status — проверить статус

**Режимы:**
.mode normal — обычный
.mode busy — занят
.mode sleeping — сплю
.mode meeting — встреча

**Инструменты:**
.stats — статистика
.analytics — аналитика
.remind — напоминание

**Списки:**
.addwhite — белый список
.addblack — чёрный список

**Настройки:**
.filter — фильтрация
.help — все команды"""
    
    await event.reply(menu_text)

@client.on(events.NewMessage(outgoing=True, pattern=r'\.mode'))
async def set_mode(event):
    global current_mode
    
    text = event.text.replace('.mode', '').strip().lower()
    modes = {
        "normal": "😊 Обычный",
        "busy": "😤 Занят",
        "sleeping": "😴 Сплю",
        "meeting": "🤝 Встреча",
    }
    
    if text in modes:
        current_mode = text
        await event.reply(f'✅ Режим: {modes[text]}')
    else:
        await event.reply('Доступные режимы:\n.mode normal\n.mode busy\n.mode sleeping\n.mode meeting')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.online'))
async def set_online(event):
    global is_online
    is_online = True
    await event.reply('✅ Онлайн!')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.offline'))
async def set_offline(event):
    global is_online
    is_online = False
    await event.reply('🌙 Оффлайн!')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.status'))
async def check_status(event):
    status = "Онлайн" if is_online else "Оффлайн"
    mode_names = {"normal": "😊 Обычный", "busy": "😤 Занят", "sleeping": "😴 Сплю", "meeting": "🤝 Встреча"}
    moscow_time = get_time().strftime("%H:%M")
    
    text = f"""📊 **СТАТУС**

Состояние: {status}
Режим: {mode_names[current_mode]}
Время: {moscow_time} (МСК)
Фильтр: {FILTER_MODE}"""
    
    await event.reply(text)

@client.on(events.NewMessage(outgoing=True, pattern=r'\.help'))
async def help_cmd(event):
    help_text = """📋 **ВСЕ КОМАНДЫ**

**Основные:**
.menu — меню
.status — статус
.online / .offline — смена статуса

**Режимы:**
.mode normal — обычный
.mode busy — занят
.mode sleeping — сплю
.mode meeting — встреча

**Инструменты:**
.stats — статистика
.analytics — аналитика
.remind минуты текст — напоминание

**Списки:**
.addwhite — белый список (ответом)
.addblack — чёрный список (ответом)

**Настройки:**
.filter — фильтрация
.db — проверить базу данных"""
    
    await event.reply(help_text)

@client.on(events.NewMessage(outgoing=True, pattern=r'\.db'))
async def check_db(event):
    """Проверка базы данных"""
    try:
        total_users = len(db.get_top_users(1000))
        total_messages = db.get_total_messages()
        white_list = db.get_white_list()
        black_list = db.get_black_list()
        
        text = f"""🗄 **БАЗА ДАННЫХ**

Пользователей: {total_users}
Сообщений: {total_messages}
Белый список: {len(white_list)}
Чёрный список: {len(black_list)}
Статус: ✅ Работает"""
        
        await event.reply(text)
    except Exception as e:
        await event.reply(f'❌ Ошибка БД: {e}')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.filter'))
async def change_filter(event):
    global FILTER_MODE
    
    text = event.text.replace('.filter', '').strip().lower()
    
    if text in ["all", "bot_only", "whitelist"]:
        FILTER_MODE = text
        await event.reply(f'🔍 Фильтр изменён: {text}')
    else:
        await event.reply(f'Текущий фильтр: {FILTER_MODE}\n\nДля смены:\n.filter all — все\n.filter bot_only — только с ботом\n.filter whitelist — белый список')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.stats'))
async def show_stats(event):
    top_users = db.get_top_users(10)
    total_messages = db.get_total_messages()
    
    stats_text = f"📊 **СТАТИСТИКА**\n\n💬 Сообщений: {total_messages}\n\nТоп собеседников:\n"
    for user_id, name, count in top_users:
        stats_text += f"• {name}: {count} сообщ.\n"
    
    await send_to_topic(TOPIC_STATS, stats_text)
    await event.reply('📊 Отправлено в тему "Статистика"!')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.analytics'))
async def show_analytics(event):
    report = analytics.generate_report()
    await event.reply(report)

@client.on(events.NewMessage(outgoing=True, pattern=r'\.remind'))
async def set_reminder(event):
    text = event.text.replace('.remind', '').strip()
    parts = text.split(' ', 1)
    
    if len(parts) >= 2:
        try:
            minutes = int(parts[0])
            reminder_text = parts[1]
            remind_at = (get_time() + timedelta(minutes=minutes)).isoformat()
            db.add_reminder(reminder_text, remind_at)
            await event.reply(f'⏰ Напомню через {minutes} мин: {reminder_text}')
        except ValueError:
            await event.reply('Формат: .remind минуты текст')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.addwhite'))
async def add_white(event):
    if event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        db.add_user(reply_msg.sender_id, (await reply_msg.get_sender()).first_name or "Пользователь")
        db.set_white(reply_msg.sender_id, True)
        sender = await reply_msg.get_sender()
        await event.reply(f'✅ {sender.first_name} в белом списке!')
    else:
        await event.reply('Ответьте на сообщение командой .addwhite')

@client.on(events.NewMessage(outgoing=True, pattern=r'\.addblack'))
async def add_black(event):
    if event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        db.add_user(reply_msg.sender_id, (await reply_msg.get_sender()).first_name or "Пользователь")
        db.set_black(reply_msg.sender_id, True)
        sender = await reply_msg.get_sender()
        await event.reply(f'🚫 {sender.first_name} в чёрном списке!')
    else:
        await event.reply('Ответьте на сообщение командой .addblack')

# Capture only the owner's own messages to explicitly permitted private contacts.
# No Telegram history fetch; no persistent storage; never mix contact contexts.
@client.on(events.NewMessage(outgoing=True))
async def remember_owner_private_reply(event):
    if not (db.get_setting("reply_drafts_enabled", False) and event.is_private):
        return
    peer_id = event.chat_id
    if peer_id != OWNER_ID and peer_id in db.get_white_list():
        recent_chat_context.add(peer_id, "owner", event.raw_text)


# === ОСНОВНОЙ ОБРАБОТЧИК ===

@client.on(events.NewMessage(incoming=True))
async def handle_messages(event):
    global is_online, FILTER_MODE
    
    if event.out:
        return
    
    if event.text and event.text.startswith('.'):
        return
    
    if not event.is_private:
        return
    
    sender = await event.get_sender()
    sender_id = event.sender_id
    sender_name = sender.first_name if sender.first_name else "Неизвестный"
    
    # Безопасность
    if security.is_banned(sender_id):
        return
    
    if not security.check_rate_limit(sender_id):
        logger.warning(f"Флуд от {sender_name}")
        return
    
    # База данных
    db.add_user(sender_id, sender_name)
    db.add_message(sender_id, event.text)
    
    # Черновики включаются владельцем и только для контактов из белого списка.
    # При активном режиме для этих контактов не отправляем старый автоответ.
    if can_prepare_draft(
        enabled=db.get_setting("reply_drafts_enabled", False),
        private=event.is_private, outgoing=event.out,
        sender_id=sender_id, owner_id=OWNER_ID,
        allowed_ids=set(db.get_white_list()), text=event.raw_text,
    ):
        previous = recent_chat_context.recent(sender_id)
        recent_chat_context.add(sender_id, "contact", event.raw_text)
        tone = db.get_setting(setting_key(sender_id), DEFAULT_STYLE)
        question = draft_question(event.raw_text, sender_name, previous, style=tone)
        suggestion = await ask_local_ai(question, tone=tone)
        if (not suggestion.startswith(("Локальная модель недоступна.", "Слишком длинный запрос"))
                and db.get_setting("reply_drafts_enabled", False)
                and sender_id in db.get_white_list()):
            try:
                draft = pending_reply_drafts.add(sender_id, sender_name, suggestion)
            except ValueError:
                logger.warning("Неподходящий черновик для отправки")
            else:
                preview = display_draft(sender_name, suggestion)
                await client.send_message(
                    "me",
                    f"{preview}\n\n"
                    f"🧑 ID контакта: {sender_id} · стиль: {tone}\n"
                    f"✅ Отправить: .senddraft {draft.draft_id}\n"
                    f"✏️ Изменить: .editdraft {draft.draft_id} НОВЫЙ ТЕКСТ\n"
                    f"👁️ Проверить: .showdraft {draft.draft_id}\n"
                    f"❌ Отменить: .canceldraft {draft.draft_id}\n"
                    "Черновик действует 30 минут после создания.",
                )
        else:
            logger.warning("Черновик не создан: модель недоступна или доступ отключён")
        return

    # Фильтрация
    white_list = db.get_white_list()
    black_list = db.get_black_list()
    
    if sender_id in black_list:
        return
    
    category = smart_filter.get_message_category(sender_id, event.text)
    
    # Белый список
    if sender_id in white_list or category == "important":
        await send_to_topic(TOPIC_IMPORTANT, f'⚡️ **ВАЖНОЕ!**\n\nОт: {sender_name}\nТекст: {event.text}\n🕐 {get_time().strftime("%H:%M")}')
        return
    
    # Спам
    if category == "spam":
        logger.info(f"Спам от {sender_name}")
        return
    
    # Обычная обработка
    if not is_online:
        await send_to_topic(TOPIC_INCOMING, f'📩 **Входящее**\n\nОт: {sender_name}\nТекст: {event.text}\n🕐 {get_time().strftime("%H:%M")}')
    else:
        await send_to_topic(TOPIC_INCOMING, f'🔔 **Сообщение**\n\nОт: {sender_name}\nТекст: {event.text}\n🕐 {get_time().strftime("%H:%M")}')

@client.on(events.NewMessage(outgoing=True, pattern=r'^\\.drafttone(?:\\s|$)'))
async def set_contact_draft_style(event):
    """Set safe, per-contact reply style, only from owner's Saved Messages."""
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    args = event.raw_text[len(".drafttone"):].strip().split()
    if not args or len(args) > 2 or not args[0].isdecimal():
        await event.reply("Формат: .drafttone ID_КОНТАКТА warm / concise / professional")
        return
    contact_id = int(args[0])
    if contact_id not in db.get_white_list():
        await event.reply("Контакт не в белом списке. Настройки не изменены.")
        return
    key = setting_key(contact_id)
    if len(args) == 1:
        await event.reply(
            f"Стиль контакта {contact_id}: {db.get_setting(key, DEFAULT_STYLE)}"
        )
        return
    try:
        selected = validated_style(args[1].lower())
    except ValueError as error:
        await event.reply(str(error))
        return
    db.set_setting(key, selected)
    await event.reply(f"✅ Стиль контакта {contact_id}: {selected}")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.drafts(?:\s|$)'))
async def toggle_reply_drafts(event):
    """Владелец включает предложения ответов в Telegram Избранном."""
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    requested = event.raw_text[len(".drafts"):].strip().lower()
    if requested not in ("on", "off"):
        state = "включены" if db.get_setting("reply_drafts_enabled", False) else "выключены"
        await event.reply(
            f"Черновики {state}. Команды: .drafts on / .drafts off. "
            "Работает только для личных чатов из белого списка (.addwhite). "
            "Предложения приходят в Избранное; собеседникам ничего не отправляется."
        )
        return
    db.set_setting("reply_drafts_enabled", requested == "on")
    if requested == "off":
        pending_reply_drafts.clear()
        recent_chat_context.clear()
    await event.reply(
        "✉️ Черновики включены для личных чатов из белого списка. "
        "Результаты придут в Избранное, отправка только после команды .senddraft НОМЕР."
        if requested == "on" else "🛑 Черновики выключены."
    )


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.editdraft(?:\s|$)'))
async def edit_reply_draft(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    arguments = event.raw_text[len('.editdraft'):].strip().split(None, 1)
    if len(arguments) != 2 or not arguments[0].isdecimal():
        await event.reply('Формат: .editdraft НОМЕР новый текст ответа')
        return
    try:
        draft = pending_reply_drafts.edit(
            int(arguments[0]), arguments[1],
            enabled=db.get_setting('reply_drafts_enabled', False),
            allowed_ids=set(db.get_white_list()),
        )
    except ValueError as error:
        await event.reply(str(error))
        return
    if draft is None:
        await event.reply('Черновик не найден, истёк или контакт больше не разрешён.')
        return
    await event.reply(
        f'✏️ Черновик #{draft.draft_id} для {draft.recipient_name} обновлён.\n\n'
        f'{draft.reply}\n\n'
        f'✅ Отправить: .senddraft {draft.draft_id}\n'
        f'❌ Отменить: .canceldraft {draft.draft_id}'
    )


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.showdraft(?:\s|$)'))
async def show_reply_draft(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    value = event.raw_text[len('.showdraft'):].strip()
    if not value.isdecimal():
        await event.reply('Формат: .showdraft НОМЕР')
        return
    draft = pending_reply_drafts.peek(int(value))
    if not (draft and db.get_setting('reply_drafts_enabled', False)
            and draft.recipient_id in db.get_white_list()):
        await event.reply('Черновик не найден, истёк или контакт больше не разрешён.')
        return
    await event.reply(
        f'👁️ Черновик #{draft.draft_id} для {draft.recipient_name}:\n\n'
        f'{draft.reply}\n\n'
        f'✅ Отправить: .senddraft {draft.draft_id}\n'
        f'✏️ Изменить: .editdraft {draft.draft_id} НОВЫЙ ТЕКСТ'
    )

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.senddraft(?:\s|$)'))
async def send_reply_draft(event):
    """One-time, owner-initiated send. Never runs from incoming chats."""
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    value = event.raw_text[len(".senddraft"):].strip()
    if not value.isdecimal():
        await event.reply("Формат: .senddraft НОМЕР (из последнего черновика)")
        return
    draft = pending_reply_drafts.take_for_send(
        int(value),
        enabled=db.get_setting("reply_drafts_enabled", False),
        allowed_ids=set(db.get_white_list()),
    )
    if draft is None:
        await event.reply("Черновик не найден, истёк, уже использован или контакт запрещён.")
        return
    try:
        await client.send_message(draft.recipient_id, draft.reply)
    except Exception:
        logger.exception("Не удалось отправить подтверждённый черновик")
        await event.reply("❌ Ошибка отправки. Черновик погашен во избежание дубля. Создай новый.")
        return
    await event.reply(f"✅ Отправлено контакту {draft.recipient_name} (черновик #{draft.draft_id}).")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.canceldraft(?:\s|$)'))
async def cancel_reply_draft(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    value = event.raw_text[len(".canceldraft"):].strip()
    if not value.isdecimal():
        await event.reply("Формат: .canceldraft НОМЕР")
        return
    removed = pending_reply_drafts.cancel(int(value))
    await event.reply("🗑️ Черновик отменён." if removed else "Черновик не найден или истёк.")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.ask(?:\s+|$)'))
async def ask_ai_command(event):
    """Обращение к бесплатной локальной модели, только из аккаунта владельца."""
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    question = event.raw_text[4:].strip()
    if not question:
        await event.reply("Напиши вопрос после .ask")
        return
    async with ai_dialogue_lock:
        history = db.get_ai_history(OWNER_ID, limit=12)
        facts = [fact for _, fact in db.list_ai_facts(OWNER_ID)]
        tone = db.get_setting("ai_tone", "warm")
        tasks = [title for _, title in db.list_ai_tasks(OWNER_ID, limit=50)]
        answer = await ask_local_ai(question, history, facts, tone, tasks)
        if not answer.startswith("Локальная модель недоступна."):
            db.add_ai_exchange(OWNER_ID, question, answer)
        await event.reply(answer[:4000])


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.forget(?:\s|$)'))
async def forget_ai_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    async with ai_dialogue_lock:
        removed = db.clear_ai_history(OWNER_ID)
    await event.reply(f"🧹 Удалила историю ИИ: {removed} сообщений. Статистика и входящие сообщения не затронуты.")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.memory(?:\s|$)'))
async def ai_memory_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    count = len(db.get_ai_history(OWNER_ID, limit=100))
    await event.reply(f"🧠 В памяти есть последние {count} реплик (показываю максимум 30). Для удаления: .forget")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.remember(?:\s|$)'))
async def remember_fact_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    fact = event.raw_text[len(".remember"):].strip()
    try:
        fact_id = db.add_ai_fact(OWNER_ID, fact)
    except ValueError as error:
        await event.reply(str(error))
        return
    await event.reply(f"🧠 Запомнила заметку #{fact_id}. Посмотреть: .memories")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.memories(?:\s|$)'))
async def list_facts_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    facts = db.list_ai_facts(OWNER_ID)
    if not facts:
        await event.reply("Пока нет сохранённых заметок. Добавить: .remember текст")
        return
    lines = [f"#{fact_id}: {fact}" for fact_id, fact in facts]
    # Telegram has a message size limit. Send manageable chunks.
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 3500:
            await event.reply(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await event.reply(chunk)


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.forgetfact(?:\s|$)'))
async def forget_fact_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    arg = event.raw_text[len(".forgetfact"):].strip()
    if not arg.isdecimal():
        await event.reply("Формат: .forgetfact номер")
        return
    removed = db.delete_ai_fact(OWNER_ID, int(arg))
    await event.reply("🧹 Заметка удалена." if removed else "Заметка не найдена.")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.forgetallfacts(?:\s|$)'))
async def forget_all_facts_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    if event.raw_text.strip() != ".forgetallfacts CONFIRM":
        await event.reply("Для удаления всех заметок напиши: .forgetallfacts CONFIRM")
        return
    removed = db.clear_ai_facts(OWNER_ID)
    await event.reply(f"🧹 Удалено заметок: {removed}")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.tone(?:\s|$)'))
async def set_ai_tone_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    from personality import PERSONAS
    tone = event.raw_text[len(".tone"):].strip().lower()
    if tone not in PERSONAS:
        current = db.get_setting("ai_tone", "warm")
        await event.reply(
            f"Текущий характер: {current}. Выбери: .tone warm / concise / professional"
        )
        return
    db.set_setting("ai_tone", tone)
    await event.reply(f"✨ Стиль общения: {tone}")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.taskadd(?:\s|$)'))
async def add_task_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    title = event.raw_text[len(".taskadd"):].strip()
    try:
        task_id = db.add_ai_task(OWNER_ID, title)
    except ValueError as error:
        await event.reply(str(error))
        return
    await event.reply(f"✅ Записала задачу #{task_id}: {title[:300]}")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.tasks(?:\s|$)'))
async def list_tasks_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    tasks = db.list_ai_tasks(OWNER_ID)
    if not tasks:
        await event.reply("🎉 Открытых задач нет. Добавить: .taskadd текст")
        return
    chunk = ""
    for task_id, title in tasks:
        line = f"#{task_id}: {title}\n"
        if len(chunk) + len(line) > 3500:
            await event.reply(chunk)
            chunk = ""
        chunk += line
    if chunk:
        await event.reply(chunk)


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.taskdone(?:\s|$)'))
async def complete_task_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    arg = event.raw_text[len(".taskdone"):].strip()
    if not arg.isdecimal():
        await event.reply("Формат: .taskdone номер")
        return
    updated = db.complete_ai_task(OWNER_ID, int(arg))
    await event.reply("✅ Задача завершена." if updated else "Открытая задача не найдена.")


@client.on(events.NewMessage(outgoing=True, pattern=r'^\.taskdelete(?:\s|$)'))
async def delete_task_command(event):
    if not is_saved_messages_owner(event, OWNER_ID):
        return
    arg = event.raw_text[len(".taskdelete"):].strip()
    if not arg.isdecimal():
        await event.reply("Формат: .taskdelete номер")
        return
    removed = db.delete_ai_task(OWNER_ID, int(arg))
    await event.reply("🗑️ Задача удалена." if removed else "Задача не найдена.")


# === ЗАПУСК ===

async def main():
    await client.start()
    logger.info("✅ Бот запущен!")
    logger.info(f"📁 Группа: {GROUP_ID}")
    logger.info(f"🔍 Фильтр: {FILTER_MODE}")
    
    scheduler = Scheduler(client, db, send_to_topic)
    await scheduler.start()
    try:
        await client.run_until_disconnected()
    finally:
        for task in scheduler.tasks:
            task.cancel()
        await asyncio.gather(*scheduler.tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())