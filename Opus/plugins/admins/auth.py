from pyrogram import filters
from pyrogram.types import Message

from Opus import app
from Opus.utils import extract_user, int_to_alpha
from Opus.utils.database import (
    delete_authuser,
    get_authuser,
    get_authuser_names,
    save_authuser,
)
from Opus.utils.decorators import AdminActual, language
from Opus.utils.inline import close_markup
from config import BANNED_USERS, adminlist


@app.on_message(filters.command("auth") & filters.group & ~BANNED_USERS)
@AdminActual
async def auth(client, message: Message, _):
    if not getattr(message, "reply_to_message", None):
        if not getattr(message, "command", None) or len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    if not user or not getattr(user, "id", None):
        return await message.reply_text(_["general_1"])
    token = await int_to_alpha(user.id)
    _check = await get_authuser_names(getattr(message.chat, "id", None))
    count = len(_check) if _check else 0
    if int(count) == 25:
        return await message.reply_text(_["auth_1"])
    if token not in (_check or []):
        assis = {
            "auth_user_id": user.id,
            "auth_name": getattr(user, "first_name", ""),
            "admin_id": getattr(getattr(message, "from_user", None), "id", 0),
            "admin_name": getattr(getattr(message, "from_user", None), "first_name", ""),
        }
        get = adminlist.get(getattr(message.chat, "id", None))
        if get:
            if user.id not in get:
                get.append(user.id)
        await save_authuser(getattr(message.chat, "id", None), token, assis)
        return await message.reply_text(_["auth_2"].format(getattr(user, "mention", getattr(user, "first_name", ""))))
    else:
        return await message.reply_text(_["auth_3"].format(getattr(user, "mention", getattr(user, "first_name", ""))))


@app.on_message(filters.command("unauth") & filters.group & ~BANNED_USERS)
@AdminActual
async def unauthusers(client, message: Message, _):
    if not getattr(message, "reply_to_message", None):
        if not getattr(message, "command", None) or len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    if not user or not getattr(user, "id", None):
        return await message.reply_text(_["general_1"])
    token = await int_to_alpha(user.id)
    deleted = await delete_authuser(getattr(message.chat, "id", None), token)
    get = adminlist.get(getattr(message.chat, "id", None))
    if get:
        if user.id in get:
            try:
                get.remove(user.id)
            except:
                pass
    if deleted:
        return await message.reply_text(_["auth_4"].format(getattr(user, "mention", getattr(user, "first_name", ""))))
    else:
        return await message.reply_text(_["auth_5"].format(getattr(user, "mention", getattr(user, "first_name", ""))))


@app.on_message(
    filters.command(["authlist", "authusers"]) & filters.group & ~BANNED_USERS
)
@language
async def authusers(client, message: Message, _):
    _wtf = await get_authuser_names(getattr(message.chat, "id", None))
    if not _wtf:
        return await message.reply_text(_["setting_4"])
    else:
        j = 0
        mystic = await message.reply_text(_["auth_6"])
        text = _["auth_7"].format(getattr(message.chat, "title", ""))
        for umm in _wtf:
            _umm = await get_authuser(getattr(message.chat, "id", None), umm)
            if not _umm:
                continue
            user_id = _umm.get("auth_user_id")
            admin_id = _umm.get("admin_id")
            admin_name = _umm.get("admin_name", "")
            try:
                user_obj = await app.get_users(user_id)
                user_name = getattr(user_obj, "first_name", str(user_id))
                j += 1
            except:
                continue
            text += f"{j}➤ {user_name}[<code>{user_id}</code>]\n"
            text += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"
        await mystic.edit_text(text, reply_markup=close_markup(_))
