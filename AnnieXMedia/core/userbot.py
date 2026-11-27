# Authored By Certified Coders © 2025
from pyrogram import Client

import config

from ..logging import LOGGER

assistants = []
assistantids = []

GROUPS_TO_JOIN = [
    "amrit_feel",
    "privatethink",
]


# Initialize userbots
class Userbot:
    def __init__(self):
        self.one = Client(
            "AnnieAssis1",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
            workers=4,
        )
        self.two = Client(
            "AnnieAssis2",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
            workers=4,
        )
        self.three = Client(
            "AnnieAssis3",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
            workers=4,
        )
        self.four = Client(
            "AnnieAssis4",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
            workers=4,
        )
        self.five = Client(
            "AnnieAssis5",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
            workers=4,
        )

    async def start_assistant(self, client: Client, index: int):
        string_attr = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ][index - 1]
        if not string_attr:
            return

        try:
            await client.start()
            for group in GROUPS_TO_JOIN:
                try:
                    await client.join_chat(group)
                except Exception:
                    pass

            assistants.append(index)

            try:
                await client.send_message(
                    config.LOGGER_ID, f"Annie's Assistant {index} Started"
                )
            except Exception:
                LOGGER(__name__).warning(
                    f"Assistant {index} can't access the log group. Please ensure assistant is added to LOGGER_ID."
                )

            me = await client.get_me()
            client.id, client.name, client.username = me.id, me.first_name, me.username
            assistantids.append(me.id)

            LOGGER(__name__).info(f"Assistant {index} Started as {client.name}")

        except Exception as e:
            LOGGER(__name__).error(f"Failed to start Assistant {index}: {e}")

    async def start(self):
        LOGGER(__name__).info("Starting Annie's Assistants...")
        await self.start_assistant(self.one, 1)
        await self.start_assistant(self.two, 2)
        await self.start_assistant(self.three, 3)
        await self.start_assistant(self.four, 4)
        await self.start_assistant(self.five, 5)

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        for client, string_attr in [
            (self.one, config.STRING1),
            (self.two, config.STRING2),
            (self.three, config.STRING3),
            (self.four, config.STRING4),
            (self.five, config.STRING5),
        ]:
            if string_attr:
                try:
                    await client.stop()
                except Exception as e:
                    LOGGER(__name__).warning(f"Error while stopping assistant: {e}")
