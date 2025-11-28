import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import LOGGER_ID
from Opus import app
from Opus.core.userbot import Userbot
from Opus.utils.ndatabase import delete_served_chat, add_served_chat, get_assistant
from strings.__init__ import LOGGERS


@app.on_message(filters.new_chat_members, group=2)
async def join_watcher(_, message: Message):
    try:
        userbot = await get_assistant(message.chat.id)
        chat = message.chat
        for members in message.new_chat_members:
            if members.id == app.id:
                count = await app.get_chat_members_count(chat.id)
                username = message.chat.username or "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"
                msg = (
                    "<blockquote><b>● ᴊᴏɪɴᴇᴅ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ 📣/b>\n\n"
                    f"<b>ᴄʜᴀᴛ ɴᴀᴍᴇ:</b> {message.chat.title}\n"
                    f"<b>ᴄʜᴀᴛ ɪᴅ:</b> {message.chat.id}\n"
                    f"<b>ᴄʜᴀᴛ ᴍᴇᴍʙᴇʀꜱ:</b> {count}<b></blockquote>"
                )

                if message.chat.username:
                    btn_link = f"https://t.me/{message.chat.username}"
                else:
                    try:
                        btn_link = await app.export_chat_invite_link(message.chat.id)
                    except:
                        btn_link = None

                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("ᴏᴘᴇɴ ᴄʜᴀᴛ", url=btn_link)]] if btn_link else None
                )

                await app.send_message(LOGGER_ID, text=msg, reply_markup=markup)
                await add_served_chat(message.chat.id)

                await userbot.join_chat(f"{username}")
                oks = await userbot.send_message(LOGGERS, "/start")
                ok = await userbot.send_message(LOGGERS, f"#{app.username}\n@{app.username}")
                await oks.delete()
                await asyncio.sleep(2)
                await ok.delete()

    except Exception as e:
        print(f"Error: {e}")


@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    try:
        userbot = await get_assistant(message.chat.id)
        left_chat_member = message.left_chat_member

        if left_chat_member and left_chat_member.id == (await app.get_me()).id:
            remove_by = message.from_user.mention if message.from_user else "ᴜɴᴋɴᴏᴡɴ"
            title = message.chat.title
            chat_id = message.chat.id

            left = (
                f"<blockquote>● <b>ʟᴇꜰᴛ ɢʀᴏᴜᴘ</b> 🎯\n\n"
                f"<b>ᴄʜᴀᴛ ᴛɪᴛʟᴇ : {title}</b>\n"
                f"<b>ᴄʜᴀᴛ ɪᴅ : {chat_id}</b>\n"
                f"ʀᴇᴍᴏᴠᴇᴅ ʙʏ : {remove_by}🪾"
            )

            await app.send_message(LOGGER_ID, text=left)
            await delete_served_chat(chat_id)
            await userbot.leave_chat(chat_id)
    except Exception:
        return
