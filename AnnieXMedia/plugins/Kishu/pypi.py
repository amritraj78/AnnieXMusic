# Authored By Certified Coders © 2025
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.logging import LOGGER


async def get_pypi_info(package_name: str):
    try:
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        client = await get_http_session()
        async with client.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.json(content_type=None)
    except Exception as e:
        LOGGER(__name__).debug(f"Error fetching PyPI information: {e}")
    return None


@app.on_message(filters.command("pypi"))
async def pypi_info_command(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**❌ Please provide a Python package name.**\n\nExample: `/pypi requests`",
            parse_mode=ParseMode.MARKDOWN
        )

    package_name = message.command[1].strip()
    if not re.match(r"^[A-Za-z0-9._-]{1,100}$", package_name):
        return await message.reply_text("❌ Invalid Python package name.")

    status = await message.reply_text("🔎 Fetching PyPI information...")
    pypi_info = await get_pypi_info(package_name)

    if pypi_info and "info" in pypi_info:
        info = pypi_info['info']
        project_urls = info.get('project_urls') or {}
        project_url = project_urls.get('Homepage') or info.get('home_page') or f"https://pypi.org/project/{package_name}/"
        if not str(project_url).startswith(("http://", "https://")):
            project_url = f"https://pypi.org/project/{package_name}/"

        safe_name = str(info.get('name', package_name)).replace("`", "'")
        safe_ver = str(info.get('version', 'N/A')).replace("`", "'")
        safe_sum = str(info.get('summary') or 'No description provided.').replace("`", "'")[:600]

        info_message = (
            f"📦 **Package Name:** `{safe_name}`\n"
            f"🆕 **Latest Version:** `{safe_ver}`\n"
            f"📝 **Description:** {safe_sum}\n"
            f"🔗 **Project URL:** [Click here]({project_url})"
        )

        await status.edit_text(info_message, parse_mode=ParseMode.MARKDOWN)
    else:
        await status.edit_text(
            "**❌ Package not found on PyPI.**\n"
            "Please check the spelling and try again.",
            parse_mode=ParseMode.MARKDOWN
        )
