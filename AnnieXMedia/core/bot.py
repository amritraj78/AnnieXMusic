# Authored By Certified Coders © 2025
import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import MenuButtonWebApp, WebAppInfo

import config
from ..logging import LOGGER


class MusicBotClient(Client):
    def __init__(self):
        super().__init__(
            name="AnnieXMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workers=16,
            max_concurrent_transmissions=4,
        )
        self.id = 0
        self.username = None
        self.name = None
        self.mention = None
        LOGGER(__name__).info("Bot client initialized.")

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
                    f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                    f"ɪᴅ : <code>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error("❌ Bot cannot access the log group/channel – add & promote it first!")
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(f"❌ Bot has failed to access the log group.\nReason: {type(exc).__name__}")
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                LOGGER(__name__).error("❌ Promote the bot as admin in the log group/channel.")
                sys.exit()
        except Exception as e:
            LOGGER(__name__).warning(f"⚠️ Could not check admin status in log group: {e}")

        if config.WEBAPP_URL.startswith("https://"):
            try:
                await self.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="🎵 Open App",
                        web_app=WebAppInfo(url=f"{config.WEBAPP_URL}/app"),
                    )
                )
                LOGGER(__name__).info(f"🌐 Telegram WebApp Menu Button set to {config.WEBAPP_URL}/app")
            except Exception as e:
                LOGGER(__name__).warning(f"⚠️ Could not set WebApp Menu Button: {e}")

        LOGGER(__name__).info(f"✅ Music Bot started as {self.name} (@{self.username})")
