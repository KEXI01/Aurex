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
    try:
        return await message.reply_text(text, **kwargs)
    except (SlowmodeWait, FloodWait):
        return None
    except Exception:
        return None


async def safe_answer_callback(callback_query, text, show_alert=False):
    try:
        return await callback_query.answer(text, show_alert=show_alert)
    except (SlowmodeWait, FloodWait):
        return None
    except Exception:
        return None


def AdminRightsCheck(mystic):
    async def wrapper(client, message):
        if await is_maintenance() is False:
            if not getattr(message, "from_user", None) or message.from_user.id not in SUDOERS:
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
            language = await get_lang(getattr(message.chat, "id", None))
            _ = get_string(language)
        except:
            _ = get_string("en")

        if getattr(message, "sender_chat", None):
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

        cmd0 = None
        if getattr(message, "command", None):
            if len(message.command) > 0 and isinstance(message.command[0], str) and message.command[0]:
                cmd0 = message.command[0]
        if cmd0 and cmd0[0] == "c":
            chat_id = await get_cmode(getattr(message.chat, "id", None))
            if chat_id is None:
                await safe_reply_text(message, _["setting_7"])
                return
            try:
                await app.get_chat(chat_id)
            except:
                await safe_reply_text(message, _["cplay_4"])
                return
        else:
            chat_id = getattr(message.chat, "id", None)
            if chat_id is None:
                await safe_reply_text(message, _["general_5"])
                return

        if not await is_active_chat(chat_id):
            await safe_reply_text(message, _["general_5"])
            return

        is_non_admin = await is_nonadmin_chat(getattr(message.chat, "id", None))
        if not is_non_admin:
            if not getattr(message, "from_user", None) or message.from_user.id not in SUDOERS:
                admins = adminlist.get(getattr(message.chat, "id", None))
                if not admins:
                    await safe_reply_text(message, _["admin_13"])
                    return
                else:
                    if message.from_user.id not in admins:
                        if await is_skipmode(getattr(message.chat, "id", None)):
                            upvote = await get_upvote_count(chat_id)
                            text = f"""<b>ᴀᴅᴍɪɴ ʀɪɢʜᴛs ɴᴇᴇᴅᴇᴅ</b>

ʀᴇғʀᴇsʜ ᴀᴅᴍɪɴ ᴄᴀᴄʜᴇ ᴠɪᴀ : /reload

» {upvote} ᴠᴏᴛᴇs ɴᴇᴇᴅᴇᴅ ғᴏʀ ᴘᴇʀғᴏʀᴍɪɴɢ ᴛʜɪs ᴀᴄᴛɪᴏɴ."""

                            command = cmd0 or ""
                            if command and command[0] == "c":
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
                            if senn:
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
            if not getattr(message, "from_user", None) or message.from_user.id not in SUDOERS:
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
            language = await get_lang(getattr(message.chat, "id", None))
            _ = get_string(language)
        except:
            _ = get_string("en")

        if getattr(message, "sender_chat", None):
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

        if not getattr(message, "from_user", None) or message.from_user.id not in SUDOERS:
            try:
                member_obj = await app.get_chat_member(getattr(message.chat, "id", None), message.from_user.id)
            except:
                return
            privileges = getattr(member_obj, "privileges", None)
            if not privileges or not getattr(privileges, "can_manage_video_chats", False):
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
            cq_msg = getattr(CallbackQuery, "message", None)
            cq_chat_id = getattr(cq_msg.chat, "id", None) if cq_msg else None
            language = await get_lang(cq_chat_id) if cq_chat_id is not None else None
            _ = get_string(language) if language else get_string("en")
        except:
            _ = get_string("en")

        if not getattr(CallbackQuery, "message", None) or getattr(CallbackQuery.message.chat, "type", None) == ChatType.PRIVATE:
            return await mystic(client, CallbackQuery, _)

        is_non_admin = await is_nonadmin_chat(getattr(CallbackQuery.message.chat, "id", None))
        if not is_non_admin:
            try:
                member_obj = await app.get_chat_member(
                    getattr(CallbackQuery.message.chat, "id", None),
                    CallbackQuery.from_user.id,
                )
            except:
                await safe_answer_callback(CallbackQuery, _["general_4"], show_alert=True)
                return

            privileges = getattr(member_obj, "privileges", None)
            if not privileges or not getattr(privileges, "can_manage_video_chats", False):
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
            language = await get_lang(getattr(message.chat, "id", None))
            _ = get_string(language)
        except:
            _ = get_string("en")

        if getattr(message.chat, "type", None) not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await mystic(client, message, *args, **kwargs)

        uid = getattr(message.from_user, "id", None)
        if uid in SUDOERS:
            return await mystic(client, message, *args, **kwargs)

        try:
            member = await app.get_chat_member(getattr(message.chat, "id", None), uid)
        except:
            await safe_reply_text(message, _["cant_creator"])
            return

        if getattr(member, "status", None) != ChatMemberStatus.OWNER:
            await safe_reply_text(message, _["creator_only"])
            return

        return await mystic(client, message, *args, **kwargs)

    return wrapper


def CreatorOnlyCB(mystic):
    async def wrapper(client, CallbackQuery, *args, **kwargs):
        try:
            cq_msg = getattr(CallbackQuery, "message", None)
            cq_chat_id = getattr(cq_msg.chat, "id", None) if cq_msg else None
            language = await get_lang(cq_chat_id) if cq_chat_id is not None else None
            _ = get_string(language) if language else get_string("en")
        except:
            _ = get_string("en")

        uid = CallbackQuery.from_user.id
        if uid in SUDOERS:
            return await mystic(client, CallbackQuery, *args, **kwargs)

        try:
            cq_msg = getattr(CallbackQuery, "message", None)
            cq_chat_id = getattr(cq_msg.chat, "id", None) if cq_msg else None
            if cq_chat_id is None:
                await safe_answer_callback(CallbackQuery, _["cant_creator"], show_alert=True)
                return
            member = await app.get_chat_member(cq_chat_id, uid)
        except:
            await safe_answer_callback(CallbackQuery, _["cant_creator"], show_alert=True)
            return

        if getattr(member, "status", None) != ChatMemberStatus.OWNER:
            await safe_answer_callback(CallbackQuery, _["creator_only_cb"], show_alert=True)
            return

        return await mystic(client, CallbackQuery, *args, **kwargs)

    return wrapper
