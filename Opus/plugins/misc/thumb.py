from pyrogram import filters
from Opus import app
from Opus.utils.database import set_thumb_setting, get_thumb_setting

@app.on_message(filters.command(["thumb", "thumbnail"]))
async def thumb_toggle(_, message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        current = await get_thumb_setting(chat_id)
        if current:
            await message.reply_text("sᴏɴɢ ᴛʜᴜᴍʙɴᴀɪʟs : Oɴ ✅\nᴛʜᴜᴍʙɴᴀɪʟ Wɪʟʟ ʙᴇ ᴠɪsɪʙʟᴇ ᴀʟᴏɴɢ Wɪᴛʜ sᴏɴɢ ɪɴғᴏ")
        else:
            await message.reply_text("Tʜᴜᴍʙɴᴀɪʟs : ᴏғғ 🚫\nᴏɴʟʏ sᴏɴɢ ɪɴғᴏ Wʟʟ ʙᴇ ᴠɪsɪʙʟᴇ ɴᴏW ɪɴ ᴛʜɪs ᴄʜᴀᴛ.")
        return

    arg = message.command[1].lower()
    if arg == "on":
        await set_thumb_setting(chat_id, True)
        await message.reply_text("sᴏɴɢ Tʜᴜᴍʙɴᴀɪʟs ᴛᴜʀɴᴇᴅ ᴏɴ 🧩 ғᴏʀ ᴛʜɪs ᴄʜᴀᴛ.")
    elif arg == "off":
        await set_thumb_setting(chat_id, False)
        await message.reply_text("ᴛʜᴜᴍʙɴᴀɪʟs ᴛᴜʀɴᴇᴅ ᴏғғ 🔖 ғᴏʀ ᴛʜɪs ᴄʜᴀᴛ.")
