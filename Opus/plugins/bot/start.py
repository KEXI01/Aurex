import time
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython import VideosSearch
import config
from Opus import app
from Opus.misc import _boot_, SUDOERS
from Opus.plugins.sudo.sudoers import sudoers_list
from Opus.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from Opus.utils.decorators.language import LanguageStart
from Opus.utils.formatters import get_readable_time
from Opus.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string


def _user_link(user):
    if user.username:
        return f"<a href='https://t.me/{user.username}'>ᴀ ᴜsᴇʀ</a>"
    return f"<a href='tg://user?id={user.id}'>>ᴀ ᴜsᴇʀ</a>"


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_photo(
                photo=config.START_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )

        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"<blockquote><b>» {_user_link(message.from_user)} sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ sᴜᴅᴏʟɪsᴛ</b>\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code></blockquote>",
                    disable_web_page_preview=True
                )
            return

        if name[0:3] == "inf":
            m = await message.reply_text("🔎")

            query = str(name).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"

            results = VideosSearch(query, limit=1)
            data = results.result()

            if not data or not data.get("result"):
                await m.delete()
                return await message.reply_text(_["general_2"].format("No results found"))

            result = data["result"][0]

            title = result["title"]
            duration = result["duration"]
            views = result["viewCount"]["short"]
            channellink = result["channel"]["link"]
            channel = result["channel"]["name"]
            link = result["link"]
            published = result["publishedTime"]

            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )

            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text=_["S_B_8"], url=link),
                        InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT),
                    ],
                ]
            )

            await m.delete()
            await message.reply(text=searched_text, reply_markup=key)

            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"<blockquote><b>» {_user_link(message.from_user)} sᴛᴀʀᴛᴇᴅ ᴛʜᴇ sᴛᴏʀᴍ ᴛᴏ ᴄʜᴇᴄᴋ sᴏɴɢ ᴅᴇᴛᴀɪʟs</b>\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code></blockquote>",
                    disable_web_page_preview=False
                )
            return

    out = private_panel(_)
    await message.reply(
        text='<blockquote><b>𝑯ᴇʏ, I’ᴍ 𝑺ᴛᴏʀᴍ, 🧸</b></blockquote>\n<blockquote><b>ʏᴏᴜʀ ᴘᴏᴡᴇʀꜰᴜʟ ᴍᴜꜱɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ. ʙᴜɪʟᴛ ᴛᴏ ʙʀɪɴɢ ʜɪ-ʀᴇs ꜱᴏᴜɴᴅ, ꜱᴍᴏᴏᴛʜ ᴄᴏɴᴛʀᴏʟꜱ, ᴀɴ ᴇʟɪᴛᴇ ʟɪꜱᴛᴇɴɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ ғᴏʀ ʏᴏᴜʀ 𝑮ʀᴏᴜᴘꜱ & 𝑪ʜᴀɴɴᴇʟs.</b></blockquote>\n<b><blockquote><a href="https://files.catbox.moe/n2l0wd.jpg">✨</a> ᴡʜᴀᴛ ɪ ᴅᴏ:\n• 𝑷ʟᴀʏs 𝑯ɪɢʜ-𝑸ᴜᴀʟɪᴛʏ 𝑴ᴜꜱɪᴄ\n• 𝑪ᴏɴᴛʀᴏʟꜱ ➕ ᴄʟᴇᴀɴ ᴘᴇʀꜰᴏʀᴍᴀɴᴄᴇ\n• ᴄᴏᴏʟ ғᴇᴀᴛᴜʀᴇꜱ ғᴏʀ ʏᴏᴜʀ ᴄʜɪᴛʏ ᴄʜᴀᴛ ᴠɪʙᴇꜱ</blockquote></b>\n<blockquote><b>📚 ɴᴇᴇᴅ ʜᴇʟᴘ ?\nᴛᴀᴘ ʜᴇʟᴘ ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴍʏ ᴄᴏᴍᴍᴀɴᴅꜱ.</b></blockquote>',
        reply_markup=InlineKeyboardMarkup(out),
    )

    if await is_on_off(2):
        if message.from_user.id in SUDOERS:
            return
        return await app.send_message(
            chat_id=config.LOGGER_ID,
            text=f"» {_user_link(message.from_user)} sᴛᴀʀᴛᴇᴅ ᴛʜᴇ sᴛᴏʀᴍ.\nᴜsᴇʀ ɪᴅ : <code>{message.from_user.id}</code>",
            disable_web_page_preview=True
        )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply(
        text=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass

            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)

                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply(
                    text=_["start_3"].format(
                        message.from_user.first_name,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()

        except Exception as ex:
            print(ex)
