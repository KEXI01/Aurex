from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []


class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="OpusXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="OpusXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="OpusXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="OpusXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="OpusXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info("🚀 Initializing assistants...")

        async def setup_assistant(client, number):
            try:
                await client.start()
                await client.join_chat("STORM_CORE")
                await client.join_chat("STORM_TECHH")
            except Exception:
                pass

            assistants.append(number)

            try:
                await client.send_message(config.LOGGER_ID, f"✅ Assistant {number} is now online.")
            except Exception:
                LOGGER(__name__).error(
                    f"❌ Assistant {number} failed to send a message to the log group. "
                    f"Ensure it's added and promoted to admin in Logs group ({config.LOGGER_ID})."
                )
                exit()

            client.id = client.me.id
            client.name = client.me.mention
            client.username = client.me.username
            assistantids.append(client.id)

            LOGGER(__name__).info(f"Assistant {number} is active as {client.name}")

        if config.STRING1:
            await setup_assistant(self.one, 1)
        if config.STRING2:
            await setup_assistant(self.two, 2)
        if config.STRING3:
            await setup_assistant(self.three, 3)
        if config.STRING4:
            await setup_assistant(self.four, 4)
        if config.STRING5:
            await setup_assistant(self.five, 5)

        LOGGER(__name__).info("All 🟢 available assistants are up now.")

    async def stop(self):
        LOGGER(__name__).info("providing rest 🔴 to assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except Exception as e:
            LOGGER(__name__).warning(f"⚠️ Error while stopping assistants: {e}")
