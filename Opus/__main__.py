import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Opus import LOGGER, app, userbot
from Opus.core.call import Signal
from Opus.misc import sudo
from Opus.plugins import ALL_MODULES
from Opus.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS

async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("⚠️ Aᴄᴛɪᴠᴀᴛɪᴏɴ Fᴀɪʟᴇᴅ » Assɪsᴛᴀɴᴛ sᴇssɪᴏɴs ᴀʀᴇ ᴍɪssɪɴɢ.")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("Opus.plugins" + all_module)
    LOGGER("Opus.plugins").info("🧩 Mᴏᴅᴜʟᴇ Cᴏɴsᴛʟᴇʟʟᴀᴛɪᴏɴ » Aʟʟ sʏsᴛᴇᴍs sʏɴᴄᴇᴅ.")
    await userbot.start()
    await Signal.start()
    try:
        await Signal.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("Opus").error(
            "🔇 Nᴏ Aᴄᴛɪᴠᴇ VC » Lᴏɢ Gʀᴏᴜᴘ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ɪs ᴅᴏʀᴍᴀɴᴛ.\n💀 Aʙᴏʀᴛɪɴɢ Oᴘᴜs Lᴀᴜɴᴄʜ..."
        )
        exit()
    except:
        pass
    await Signal.decorators()
    LOGGER("Opus").info(
        "⚡ sᴛᴏʀᴍ ᴏɴʟɪɴᴇ » Oᴘᴜs ᴍᴜsɪᴄ sᴇǫᴜᴇɴᴄᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ.\n☁️ Pᴀʀᴛ ᴏғ Sᴛᴏʀᴍ Sᴇʀᴠᴇʀs × Oᴘᴜs Pʀᴏᴊᴇᴄᴛ."
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("Opus").info("🌩️ Cʏᴄʟᴇ Cʟᴏsᴇᴅ » Oᴘᴜs sʟᴇᴇᴘs ᴜɴᴅᴇʀ ᴛʜᴇ sᴛᴏʀᴍ.")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
