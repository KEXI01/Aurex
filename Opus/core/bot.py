import os
import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode

import config
from ..logging import LOGGER


class Signal(Client):
    def __init__(self):
        super().__init__(
            name="OpusMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            workers=30,
            max_concurrent_transmissions=7,
            parse_mode=ParseMode.HTML,
        )
        LOGGER(__name__).info("🧠 Oᴘᴜs ᴀssɪsᴛᴀɴᴛ ᴇɴɢɪɴᴇ ɪɴɪᴛɪᴀʟɪᴢᴇᴅ...")

    async def start(self):
        await super().start()

        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<b>Oᴘᴜs Bᴏᴛ ɪs ʀᴇᴀᴅʏ ᴛᴏ ᴠɪʙᴇ ᴏɴ 🍁</b>\n\n"
                    f"• ɴᴀᴍᴇ : {self.name}\n"
                    f"• ᴜsᴇʀɴᴀᴍᴇ : @{self.username}\n"
                    f"• ɪᴅ : <code>{self.id}</code>"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "🚫 Lᴏɢɢᴇʀ ᴄʜᴀᴛ ɴᴏᴛ ᴀᴄᴄᴇssɪʙʟᴇ. ᴀᴅᴅ Bᴏᴛ ᴛʜᴇʀᴇ & ᴘʀᴏᴍᴏᴛᴇ ɪᴛ ғɪʀsᴛ."
            )
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(
                f"❌ Fᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ sᴛᴀʀᴛᴜᴘ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ: {type(exc).__name__}"
            )
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    "⚠️ Bᴏᴛ ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ ɪɴ ʟᴏɢɢᴇʀ ᴄʜᴀᴛ ᴛᴏ sᴇɴᴅ ʀᴇᴘᴏʀᴛs."
                )
                sys.exit()
        except Exception as e:
            LOGGER(__name__).error(
                f"❌ Eʀʀᴏʀ ᴄʜᴇᴄᴋɪɴɢ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs: {e}"
            )
            sys.exit()

        LOGGER(__name__).info(f"🎧 Oᴘᴜs ʙᴏᴛ ʟᴀᴜɴᴄʜᴇᴅ ᴀs {self.name} (@{self.username})")
