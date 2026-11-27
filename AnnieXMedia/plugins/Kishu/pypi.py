# Authored By Certified Coders © 2025
import httpx
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from AnnieXMedia import app


async def get_pypi_info(package_name: str):
    try:
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Error fetching PyPI information: {e}")
    return None


@app.on_message(filters.command("pypi"))
async def pypi_info_command(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**❌ Please provide a Python package name.**\n\nExample: `/pypi requests`",
            parse_mode=ParseMode.MARKDOWN
        )

    package_name = message.command[1].strip()
    status = await message.reply_text("🔎 Fetching PyPI information...")
    pypi_info = await get_pypi_info(package_name)

    if pypi_info and "info" in pypi_info:
        info = pypi_info['info']
        project_urls = info.get('project_urls') or {}
        project_url = project_urls.get('Homepage') or info.get('home_page') or f"https://pypi.org/project/{package_name}/"

        info_message = (
            f"📦 **Package Name:** `{info.get('name', package_name)}`\n"
            f"🆕 **Latest Version:** `{info.get('version', 'N/A')}`\n"
            f"📝 **Description:** {info.get('summary') or 'No description provided.'}\n"
            f"🔗 **Project URL:** [Click here]({project_url})"
        )

        await status.edit_text(info_message, parse_mode=ParseMode.MARKDOWN)
    else:
        await status.edit_text(
            "**❌ Package not found on PyPI.**\n"
            "Please check the spelling and try again.",
            parse_mode=ParseMode.MARKDOWN
        )
