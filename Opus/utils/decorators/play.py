import asyncio
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    ChatWriteForbidden,
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
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if message.sender_chat:
                upl = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("How To Fix ?", callback_data="SignalmousAdmin")]]
                )
                return await safe_reply(message, _["general_3"], upl)

            if await is_maintenance() is False and message.from_user.id not in SUDOERS:
                return await safe_reply(
                    message,
                    text=f"{app.mention} ɪs uɴᴅᴇʀ ᴍaɪɴᴛᴇɴᴀɴᴄᴇ.\nPlease visit <a href={SUPPORT_CHAT}>support chat for latest updates & discussions</a>.",
                    disable_web_page_preview=True
                )

            try:
                await message.delete()
            except:
                pass

            audio = (message.reply_to_message.audio or message.reply_to_message.voice) if message.reply_to_message else None
            video = (message.reply_to_message.video or message.reply_to_message.document) if message.reply_to_message else None
            url = await YouTube.url(message)

            if not (audio or video or url):
                if len(message.command) < 2:
                    if "stream" in message.command:
                        return await safe_reply(message, _["str_1"])
                    buttons = botplaylist_markup(_)
                    return await safe_reply_photo(
                        message, PLAYLIST_IMG_URL, _["play_18"], buttons
                    )

            if message.command[0][0] == "c":
                chat_id = await get_cmode(message.chat.id)
                if not chat_id:
                    return await safe_reply(message, _["setting_7"])
                try:
                    chat = await app.get_chat(chat_id)
                    channel = chat.title
                except Exception:
                    return await safe_reply(message, _["cplay_4"])
            else:
                chat_id = message.chat.id
                channel = None

            playmode = await get_playmode(message.chat.id)
            playty = await get_playtype(message.chat.id)

            if playty != "Everyone" and message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins or message.from_user.id not in admins:
                    return await safe_reply(message, _["play_4"])

            cmd = (message.command[0] if message.command else "").lstrip("/.!").lower()
            video_cmds = {"vplay", "cvplay", "vplayforce", "cvplayforce"}
            channel_cmds = {"cplay", "cvplay", "cplayforce", "cvplayforce"}
            force_cmds = {"playforce", "vplayforce", "cplayforce", "cvplayforce"}
            is_video = True if (cmd in video_cmds or "-v" in (message.text or "").lower()) else None
            fplay = True if cmd in force_cmds else None

            try:
                bot_member = await app.get_chat_member(chat_id, (await app.get_me()).id)
                if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                    return await safe_reply(message, "🛑 Please promote Storm Music with Proper admin rights to start Streaming 🎵.")
            except ChatAdminRequired:
                pass
            except Exception:
                pass


            if not await is_active_chat(chat_id):
                userbot = await get_assistant(chat_id)
                
                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                    if member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
                        return await safe_reply(
                            message,
                            _["call_2"].format(app.mention, userbot.id, userbot.name, userbot.username)
                        )
                except ChatAdminRequired:
                    return await safe_reply(message, "🛑 Storm Music must have admin rights to check assistant's membership status.")
                except UserNotParticipant:
                    invite_link = links.get(chat_id)

                    if not invite_link:
                        if message.chat.username:
                            invite_link = message.chat.username
                        else:
                            try:
                                invite_link = await app.export_chat_invite_link(chat_id)
                            except ChatAdminRequired:
                                return await safe_reply(message, _["call_1"])
                            except Exception as e:
                                return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))

                    if invite_link and invite_link.startswith("https://t.me/+"):
                        invite_link = invite_link.replace("https://t.me/+", "https://t.me/joinchat/")

                    links[chat_id] = invite_link
                    msg = await safe_reply(message, _["call_4"].format(app.mention))

                    try:
                        await userbot.join_chat(invite_link) 
                    except InviteRequestSent:
                        try:
                            await app.approve_chat_join_request(chat_id, userbot.id)
                        except Exception as e:
                            return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))
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
                        return await safe_reply(message, "🚫 Assistant has joined too many chats.")
                    except ChatAdminRequired:
                        return await safe_reply(message, _["call_1"])
                    except RPCError as e:
                        return await safe_reply(message, f"🚫 RPC Error occurred: <code>{e}</code>")
                    except Exception as e:
                        return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))

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
            error_message = f"🚫 <b>Unexpected Error:</b>\n<pre>{str(ex)}</pre>"
            await safe_reply(message, error_message, disable_web_page_preview=True)

    return wrapper
