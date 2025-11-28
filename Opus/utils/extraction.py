from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, User
from Opus import app

async def extract_user(m: Message) -> User:
    if m.reply_to_message:
        return m.reply_to_message.from_user

    text = m.text or ""
    entities = m.entities or []

    if text.startswith("/") and len(entities) > 1:
        ent = entities[1]
    elif len(entities) > 0:
        ent = entities[0]
    else:
        ent = None

    if ent and ent.type == MessageEntityType.TEXT_MENTION:
        return await app.get_users(ent.user.id)

    if m.command and len(m.command) > 1:
        arg = m.command[1]
        if arg.isdecimal():
            return await app.get_users(int(arg))
        return await app.get_users(arg)

    return None
