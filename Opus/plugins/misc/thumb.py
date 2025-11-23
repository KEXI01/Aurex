from pyrogram import filters
from Opus import app
from Opus.utils.database import set_thumb_setting, get_thumb_setting

@app.on_message(filters.command(["thumb", "thumbnail"]))
async def thumb_toggle(_, message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        current = await get_thumb_setting(chat_id)
        if current:
            await message.reply_text("Thumb: ON 🟢\nThumbnails will be sent along with songs.")
        else:
            await message.reply_text("Thumb: OFF🔴\nOnly song info caption with controls will be sent.")
        return

    arg = message.command[1].lower()
    if arg == "on":
        await set_thumb_setting(chat_id, True)
        await message.reply_text("Thumb: ON🟩\nThumbnails will now appear with songs.")
    elif arg == "off":
        await set_thumb_setting(chat_id, False)
        await message.reply_text("Thumb: OFF🟥\nSongs will now send only info captions with playback control buttons.")
