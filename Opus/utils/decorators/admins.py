from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import SlowmodeWait, FloodWait
import asyncio

from Opus import app
from Opus.misc import SUDOERS, db
from Opus.utils.database import (
    get_authuser_names,
    get_cmode,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_maintenance,
    is_nonadmin_chat,
    is_skipmode,
)
from config import SUPPORT_CHAT, adminlist, confirmer
from strings import get_string

from ..formatters import int_to_alpha

async def safe_reply_text(message, text, **kwargs):
    """Safely send a reply message with proper error handling for rate limits"""
    try:
        return await message.reply_text(text, **kwargs)
    except (SlowmodeWait, FloodWait):
        return None
    except Exception:
        return None

async def safe_answer_callback(callback_query, text, show_alert=False):
    """Safely answer callback queries with proper error handling"""
    try:
        return await callback_query.answer(text, show_alert=show_alert)
    except (SlowmodeWait, FloodWait):
        return None
    except Exception:
        return None

def AdminRightsCheck(mystic):
    async def wrapper(client, message):
        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                await safe_reply_text(
                    message,
                    f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )
                return

        try:
            await message.delete()
        except:
            pass

        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
        except:
            _ = get_string("en")
            
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="SignalmousAdmin",
                        ),
                    ]
                ]
            )
            await safe_reply_text(message, _["general_3"], reply_markup=upl)
            return
            
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                await safe_reply_text(message, _["setting_7"])
                return
            try:
                await app.get_chat(chat_id)
            except:
                await safe_reply_text(message, _["cplay_4"])
                return
        else:
            chat_id = message.chat.id
            
        if not await is_active_chat(chat_id):
            await safe_reply_text(message, _["general_5"])
            return
            
        is_non_admin = await is_nonadmin_chat(message.chat.id)
        if not is_non_admin:
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    await safe_reply_text(message, _["admin_13"])
                    return
                else:
                    if message.from_user.id not in admins:
                        if await is_skipmode(message.chat.id):
                            upvote = await get_upvote_count(chat_id)
                            text = f"""<b>ᴀᴅᴍɪɴ ʀɪɢʜᴛs ɴᴇᴇᴅᴇᴅ</b>

ʀᴇғʀᴇsʜ ᴀᴅᴍɪɴ ᴄᴀᴄʜᴇ ᴠɪᴀ : /reload

» {upvote} ᴠᴏᴛᴇs ɴᴇᴇᴅᴇᴅ ғᴏʀ ᴘᴇʀғᴏʀᴍɪɴɢ ᴛʜɪs ᴀᴄᴛɪᴏɴ."""

                            command = message.command[0]
                            if command[0] == "c":
                                command = command[1:]
                            if command == "speed":
                                await safe_reply_text(message, _["admin_14"])
                                return
                            MODE = command.title()
                            upl = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            text="ᴠᴏᴛᴇ",
                                            callback_data=f"ADMIN  UpVote|{chat_id}_{MODE}",
                                        ),
                                    ]
                                ]
                            )
                            if chat_id not in confirmer:
                                confirmer[chat_id] = {}
                            try:
                                vidid = db[chat_id][0]["vidid"]
                                file = db[chat_id][0]["file"]
                            except:
                                await safe_reply_text(message, _["admin_14"])
                                return
                            senn = await safe_reply_text(message, text, reply_markup=upl)
                            if senn:  # Only add to confirmer if message was sent successfully
                                confirmer[chat_id][senn.id] = {
                                    "vidid": vidid,
                                    "file": file,
                                }
                            return
                        else:
                            await safe_reply_text(message, _["admin_14"])
                            return

        return await mystic(client, message, _, chat_id)

    return wrapper


def AdminActual(mystic):
    async def wrapper(client, message):
        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                await safe_reply_text(
                    message,
                    f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )
                return

        try:
            await message.delete()
        except:
            pass

        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
        except:
            _ = get_string("en")
            
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="SignalmousAdmin",
                        ),
                    ]
                ]
            )
            await safe_reply_text(message, _["general_3"], reply_markup=upl)
            return

        if message.from_user.id not in SUDOERS:
            try:
                member = (
                    await app.get_chat_member(message.chat.id, message.from_user.id)
                ).privileges
            except:
                return
            if not member.can_manage_video_chats:
                await safe_reply_text(message, _["general_4"])
                return
                
        return await mystic(client, message, _)

    return wrapper


def ActualAdminCB(mystic):
    async def wrapper(client, CallbackQuery):
        if await is_maintenance() is False:
            if CallbackQuery.from_user.id not in SUDOERS:
                await safe_answer_callback(
                    CallbackQuery,
                    f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    show_alert=True,
                )
                return
                
        try:
            language = await get_lang(CallbackQuery.message.chat.id)
            _ = get_string(language)
        except:
            _ = get_string("en")
            
        if CallbackQuery.message.chat.type == ChatType.PRIVATE:
            return await mystic(client, CallbackQuery, _)
            
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            try:
                a = (
                    await app.get_chat_member(
                        CallbackQuery.message.chat.id,
                        CallbackQuery.from_user.id,
                    )
                ).privileges
            except:
                await safe_answer_callback(CallbackQuery, _["general_4"], show_alert=True)
                return
                
            if not a.can_manage_video_chats:
                if CallbackQuery.from_user.id not in SUDOERS:
                    token = await int_to_alpha(CallbackQuery.from_user.id)
                    _check = await get_authuser_names(CallbackQuery.from_user.id)
                    if token not in _check:
                        await safe_answer_callback(CallbackQuery, _["general_4"], show_alert=True)
                        return
                        
        return await mystic(client, CallbackQuery, _)

    return wrapper


def CreatorOnly(mystic):
    async def wrapper(client, message, *args, **kwargs):
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
        except:
            _ = get_string("en")

        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await mystic(client, message, *args, **kwargs)

        uid = message.from_user.id
        if uid in SUDOERS:
            return await mystic(client, message, *args, **kwargs)

        try:
            member = await app.get_chat_member(message.chat.id, uid)
        except:
            await safe_reply_text(message, _["cant_creator"])
            return

        if member.status != ChatMemberStatus.OWNER:
            await safe_reply_text(message, _["creator_only"])
            return

        return await mystic(client, message, *args, **kwargs)

    return wrapper


def CreatorOnlyCB(mystic):
    async def wrapper(client, CallbackQuery, *args, **kwargs):
        try:
            language = await get_lang(CallbackQuery.message.chat.id)
            _ = get_string(language)
        except:
            _ = get_string("en")

        uid = CallbackQuery.from_user.id
        if uid in SUDOERS:
            return await mystic(client, CallbackQuery, *args, **kwargs)

        try:
            member = await app.get_chat_member(CallbackQuery.message.chat.id, uid)
        except:
            await safe_answer_callback(CallbackQuery, _["cant_creator"], show_alert=True)
            return

        if member.status != ChatMemberStatus.OWNER:
            await safe_answer_callback(CallbackQuery, _["creator_only_cb"], show_alert=True)
            return

        return await mystic(client, CallbackQuery, *args, **kwargs)

    return wrapper
