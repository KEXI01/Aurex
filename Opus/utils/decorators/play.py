import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    ChatWriteForbidden,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import YouTube, app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from Opus.utils.inline import botplaylist_markup
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

links = {}


async def safe_reply(msg, text, markup=None, **kwargs):
    try:
        return await msg.reply_text(text, reply_markup=markup, **kwargs)
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


async def safe_reply_photo(msg, photo, caption, buttons=None):
    try:
        return await msg.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


def PlayWrapper(command):
    async def wrapper(client, message):
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        # Anonymous check
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [[InlineKeyboardButton("ʜᴏᴡ ᴛᴏ ғɪx ?", callback_data="SignalmousAdmin")]]
            )
            return await safe_reply(message, _["general_3"], upl)

        # Maintenance check
        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                return await safe_reply(
                    message,
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴜᴘᴅᴀᴛᴇs.",
                    disable_web_page_preview=True,
                )

        # Try delete user command
        try:
            await message.delete()
        except:
            pass

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        if not (audio_telegram or video_telegram or url):
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await safe_reply(message, _["str_1"])
                buttons = botplaylist_markup(_)
                return await safe_reply_photo(message, PLAYLIST_IMG_URL, _["play_18"], buttons)

        # Channel Play
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if not chat_id:
                return await safe_reply(message, _["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
                channel = chat.title
            except:
                return await safe_reply(message, _["cplay_4"])
        else:
            chat_id = message.chat.id
            channel = None

        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)

        # Admin Check
        if playty != "Everyone" and message.from_user.id not in SUDOERS:
            admins = adminlist.get(message.chat.id)
            if not admins:
                return await safe_reply(message, _["admin_13"])
import asyncio
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelsTooMuch,
    RPCError,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import YouTube, app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from Opus.utils.inline import botplaylist_markup
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

links = {}

def PlayWrapper(command):
    async def wrapper(client, message):
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if message.sender_chat:
                return await message.reply_text(
                    _["general_3"],
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="How To Fix ?", callback_data="SignalmousAdmin")]]
                    )
                )

            if await is_maintenance() is False and message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    f"{app.mention} ɪs uɴᴅᴇʀ ᴍaɪɴᴛᴇɴᴀɴᴄᴇ.\nPlease visit <a href={SUPPORT_CHAT}>support chat for latest updates & discussions</a>.",
                    disable_web_page_preview=True
                )

            try:
                await message.delete()
            except:
                pass

            audio = (message.reply_to_message.audio or message.reply_to_message.voice) if message.reply_to_message else None
            video = (message.reply_to_message.video or message.reply_to_message.document) if message.reply_to_message else None
            url = await YouTube.url(message)

            if not audio and not video and not url:
                if len(message.command) < 2:
                    if "stream" in message.command:
                        return await message.reply_text(_["str_1"])
                    return await message.reply_photo(
                        photo=PLAYLIST_IMG_URL,
                        caption=_["play_18"],
                        reply_markup=InlineKeyboardMarkup(botplaylist_markup(_)),
                    )

            if message.command[0][0] == "c":
                chat_id = await get_cmode(message.chat.id)
                if not chat_id:
                    return await message.reply_text(_["setting_7"])
                try:
                    chat = await app.get_chat(chat_id)
                    channel = chat.title
                except:
                    return await message.reply_text(_["cplay_4"])
            else:
                chat_id = message.chat.id
                channel = None

            playmode = await get_playmode(message.chat.id)
            playty = await get_playtype(message.chat.id)
            if playty != "Everyone" and message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins or message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

            is_video = (
                True if message.command[0][0] == "v" or "-v" in message.text
                else (True if message.command[0][1] == "v" else None)
            )
            fplay = True if message.command[0][-1] == "e" else None

            try:
                bot_member = await app.get_chat_member(chat_id, (await app.get_me()).id)
                if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                    return await message.reply_text("🛑 Please promote Storm Music with Proper admin rights to start Streaming 🎵.")
            except:
                pass

            if not await is_active_chat(chat_id):
                userbot = await get_assistant(chat_id)
                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                    if member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
                        return await message.reply_text(
                            _["call_2"].format(app.mention, userbot.id, userbot.name, userbot.username)
                        )
                except ChatAdminRequired:
                    return await message.reply_text("🛑 Storm Music must have admin rights to check assistant's membership status.")
                except UserNotParticipant:
                    invite_link = links.get(chat_id)

                    if not invite_link:
                        if message.chat.username:
                            invite_link = message.chat.username
                        else:
                            try:
                                invite_link = await app.export_chat_invite_link(chat_id)
                            except ChatAdminRequired:
                                return await message.reply_text(_["call_1"])
                            except:
                                return await message.reply_text(_["call_3"].format(app.mention, "Error"))

                    if invite_link.startswith("https://t.me/+"):
                        invite_link = invite_link.replace("https://t.me/+", "https://t.me/joinchat/")

                    links[chat_id] = invite_link
                    msg = await message.reply_text(_["call_4"].format(app.mention))
                    try:
                        await userbot.join_chat(invite_link)
                    except InviteRequestSent:
                        try:
                            await app.approve_chat_join_request(chat_id, userbot.id)
                        except:
                            return await message.reply_text(_["call_3"].format(app.mention, "Error"))
                        await asyncio.sleep(1)
                        await msg.edit(_["call_5"].format(app.mention))
                    except UserAlreadyParticipant:
                        pass
                    except ChannelsTooMuch:
                        note = f"<b>Too many joined groups/channels</b>\n🧹 Please run /cleanassistants to clean."
                        for sudo_id in SUDOERS:
                            try:
                                await app.send_message(sudo_id, note)
                            except:
                                pass
                        return await message.reply_text("🚫 Assistant has joined too many chats.")
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except RPCError:
                        return await message.reply_text("🚫 RPC Error occurred.")

            return await command(
                client,
                message,
                _,
                chat_id,
                is_video,
                channel,
                playmode,
                url,
                fplay,
            )

        except Exception as ex:
            try:
                await message.reply_text(
                    f"🚫 <b>Unexpected Error:</b>\n<pre>{str(ex)}</pre>",
                    disable_web_page_preview=True,
                )
            except:
                pass

    return wrapper
