# Authored By Certified Coders © 2025
from typing import Optional
from pyrogram import Client

import config

from ..logging import LOGGER

assistants = []
assistantids = []

GROUPS_TO_JOIN = [
    "amrit_feel",
    "privatethink",
]


def _make_assistant(name: str, session_str: Optional[str]) -> Optional[Client]:
    s = (session_str or "").strip()
    if not s or s.lower() == "none":
        return None
    return Client(
        name,
        config.API_ID,
        config.API_HASH,
        session_string=s,
        no_updates=True,
        workers=4,
    )


class Userbot:
    def __init__(self):
        self.one = _make_assistant("AnnieAssis1", config.STRING1)
        self.two = _make_assistant("AnnieAssis2", config.STRING2)
        self.three = _make_assistant("AnnieAssis3", config.STRING3)
        self.four = _make_assistant("AnnieAssis4", config.STRING4)
        self.five = _make_assistant("AnnieAssis5", config.STRING5)

    async def start_assistant(self, client: Optional[Client], index: int):
        if client is None:
            return

        try:
            await client.start()
            for group in GROUPS_TO_JOIN:
                try:
                    await client.join_chat(group)
                except Exception:
                    pass

            if index not in assistants:
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
            if me.id not in assistantids:
                assistantids.append(me.id)

            LOGGER(__name__).info(f"Assistant {index} Started as {client.name}")

        except Exception as e:
            LOGGER(__name__).error(f"Failed to start Assistant {index}: {e}")

    async def start(self):
        LOGGER(__name__).info("Starting Annie's Assistants...")
        for idx, client in enumerate((self.one, self.two, self.three, self.four, self.five), 1):
            await self.start_assistant(client, idx)

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        for client in (self.one, self.two, self.three, self.four, self.five):
            if client is not None:
                try:
                    await client.stop()
                except Exception as e:
                    LOGGER(__name__).warning(f"Error while stopping assistant: {e}")
