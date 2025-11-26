from pyrogram import filters
from Opus import app
from Opus.utils.database import set_thumb_setting, get_thumb_setting, get_lang
from strings import get_string
from Opus.utils.decorators import CreatorOnly

@app.on_message(filters.command(["thumb", "thumbnail"]))
@CreatorOnly
async def thumb_toggle(_, message):
    chat_id = message.chat.id

    try:
        language = await get_lang(chat_id)
        _ = get_string(language)
    except:
        _ = get_string("en")

    if len(message.command) < 2:
        try:
            current = await get_thumb_setting(chat_id)
        except:
            await message.reply_text(_["cant_creator"])
            return

        if current:
            await message.reply_text(_["thumb_status_on"])
        else:
            await message.reply_text(_["thumb_status_off"])
        return

    arg = message.command[1].lower()
    if arg == "on":
        await set_thumb_setting(chat_id, True)
        await message.reply_text(_["thumb_on"])
    elif arg == "off":
        await set_thumb_setting(chat_id, False)
        await message.reply_text(_["thumb_off"])
    else:
        await message.reply_text(_["usage"])
