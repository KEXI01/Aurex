import asyncio
import time

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import CallbackQuery, Message

from Opus import app
from Opus.core.call import Signal
from Opus.misc import db
from Opus.utils.database import get_assistant, get_authuser_names, get_cmode
from Opus.utils.decorators import ActualAdminCB, AdminActual, language
from Opus.utils.formatters import alpha_to_int, get_readable_time
from config import BANNED_USERS, adminlist, lyrical



rel = {}

@app.on_message(
    filters.command(["admincache", "reload", "refresh"], prefixes=["/"])
    & filters.group
    & ~BANNED_USERS
)
@language
async def reload_admin_cache(client, message: Message, _):
    try:
        if message.chat.id in rel and rel[message.chat.id] > time.time():
            left = get_readable_time((int(rel[message.chat.id]) - int(time.time())))
            return await message.reply_text(_["reload_1"].format(left))

        adminlist[message.chat.id] = []
        async for user in app.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
            if user.privileges and user.privileges.can_manage_video_chats:
                adminlist[message.chat.id].append(user.user.id)

        authusers = await get_authuser_names(message.chat.id)
        for user in authusers:
            user_id = await alpha_to_int(user)
            adminlist[message.chat.id].append(user_id)

        rel[message.chat.id] = int(time.time()) + 180
        await message.reply_text(_["reload_2"])
    except Exception:
        await message.reply_text(_["reload_3"])


# ── /reboot ──
@app.on_message(filters.command(["reboot"]) & filters.group & ~BANNED_USERS)
@AdminActual
async def restartbot(client, message: Message, _):
    mystic = await message.reply_text(_["reload_4"].format(app.mention))
    await asyncio.sleep(1)
    
    try:
        # Clear main chat database
        db[message.chat.id] = []
        
        # Stop stream with enhanced call system
        await Signal.stop_stream(message.chat.id)
        
        # Clear from active calls tracking
        Signal.active_calls.discard(message.chat.id)
        
    except Exception as e:
        # Fallback to force stop if needed
        try:
            await Signal.force_stop_stream(message.chat.id)
        except:
            pass
    
    # Resolve userbot peer for main chat
    userbot = await get_assistant(message.chat.id)
    try:
        if message.chat.username:
            await userbot.resolve_peer(message.chat.username)
        else:
            await userbot.resolve_peer(message.chat.id)
    except:
        pass
    
    # Handle channel mode if enabled
    chat_id = await get_cmode(message.chat.id)
    if chat_id:
        try:
            got = await app.get_chat(chat_id)
            
            # Clear channel mode database
            db[chat_id] = []
            
            # Stop channel mode stream
            await Signal.stop_stream(chat_id)
            Signal.active_calls.discard(chat_id)
            
        except Exception as e:
            try:
                await Signal.force_stop_stream(chat_id)
            except:
                pass
        
        # Resolve userbot peer for channel mode
        userbot = await get_assistant(chat_id)
        try:
            if got.username:
                await userbot.resolve_peer(got.username)
            else:
                await userbot.resolve_peer(chat_id)
        except:
            pass
    
    return await mystic.edit_text(_["reload_5"].format(app.mention))

# ── Close Button Callback ──
@app.on_callback_query(filters.regex("close") & ~BANNED_USERS)
async def close_menu(_, query: CallbackQuery):
    try:
        await query.answer()
        await query.message.delete()
        msg = await query.message.reply_text(f"✅ ᴄʟᴏꜱᴇᴅ ʙʏ : {query.from_user.mention}")
        await asyncio.sleep(2)
        await msg.delete()
    except:
        pass


# ── Stop Download Callback ──
@app.on_callback_query(filters.regex("stop_downloading") & ~BANNED_USERS)
@ActualAdminCB
async def stop_download(_, query: CallbackQuery, _lang):
    task = lyrical.get(query.message.id)
    if not task:
        return await query.answer(_lang["tg_4"], show_alert=True)

    if task.done() or task.cancelled():
        return await query.answer(_lang["tg_5"], show_alert=True)

    try:
        task.cancel()
        lyrical.pop(query.message.id, None)
        await query.answer(_lang["tg_6"], show_alert=True)
        return await query.edit_message_text(_lang["tg_7"].format(query.from_user.mention))
    except:
        return await query.answer(_lang["tg_8"], show_alert=True)
