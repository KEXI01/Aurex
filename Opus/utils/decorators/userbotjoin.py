import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
    RPCError,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client, filters
from Opus import YouTube, app
from Opus.misc import SUDOERS
from Opus.utils.ndatabase import (
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


def UserbotWrapper(command):
    async def wrapper(client, message):
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪꜱ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪꜱɪᴛ [ꜱᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ]({SUPPORT_CHAT}) ꜰᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀꜱᴏɴ.",
                    disable_web_page_preview=True,
                )

        try:
            await message.delete()
        except:
            pass

        chat_id = message.chat.id

        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            
            try:
                get = await app.get_chat_member(chat_id, userbot.id)
                
                if (
                    get.status == ChatMemberStatus.BANNED
                    or get.status == ChatMemberStatus.RESTRICTED
                ):
                    return await message.reply_text(
                        _["call_2"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text="ᴜɴʙᴀɴ ᴀssɪsᴛᴀɴᴛ",
                                        callback_data=f"unban_assistant",
                                    )
                                ]
                            ]
                        ),
                    )
            except ChatAdminRequired:
                return await message.reply_text(
                    "**ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ ᴡɪᴛʜ ɪɴᴠɪᴛᴇ ᴘᴏᴡᴇʀ ᴛᴏ ᴀᴅᴅ ᴍʏ ᴀꜱꜱɪꜱᴛᴀɴᴛ!**"
                )
            except UserNotParticipant:
                invitelink = links.get(chat_id)

                if not invitelink:
                    if message.chat.username:
                        invitelink = message.chat.username
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(
                                "**ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ ᴡɪᴛʜ ɪɴᴠɪᴛᴇ ᴘᴏᴡᴇʀ ᴛᴏ ᴀᴅᴅ ᴍʏ ᴀꜱꜱɪꜱᴛᴀɴᴛ!**."
                            )
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(app.mention, type(e).__name__)
                            )

                if invitelink and invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                
                links[chat_id] = invitelink

                myu = await message.reply_text("**ᴀꜱꜱɪꜱᴛᴀɴᴛ ɪꜱ ᴊᴏɪɴɪɴɢ** ⏳")
                
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                    
                    await myu.delete()
                    await message.reply_text(
                        f"{app.mention} **ᴀꜱꜱɪꜱᴛᴀɴᴛ ᴊᴏɪɴᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!** ✅"
                    )
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.delete()
                    await message.reply_text(
                        f"{app.mention} **ᴀꜱꜱɪꜱᴛᴀɴᴛ ᴊᴏɪɴᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!** ✅"
                    )
                except UserAlreadyParticipant:
                    await myu.delete()
                    await message.reply_text(
                        f"{app.mention} **ᴀꜱꜱɪꜱᴛᴀɴᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ ᴄʜᴀᴛ!**"
                    )
                except RPCError as e:
                    await myu.delete()
                    return await message.reply_text(
                        f"{app.mention} **ᴇʀʀᴏʀ ᴊᴏɪɴɪɴɢ ᴀꜱꜱɪꜱᴛᴀɴᴛ:** `{e}`"
                    )
                except Exception as e:
                    await myu.delete()
                    return await message.reply_text(
                        _["call_3"].format(app.mention, type(e).__name__)
                    )

            try:
                await userbot.resolve_peer(chat_id)
            except:
                pass

        return await command(client, message, _, chat_id)

    return wrapper
    
