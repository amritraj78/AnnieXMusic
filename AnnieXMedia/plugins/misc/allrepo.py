# Authored By Certified Coders © 2025
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import LinkPreviewOptions, Message
from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.downloader import get_http_session
from AnnieXMedia.utils.security import validate_github_username


def chunk_string(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _clean_md(text: str) -> str:
    return text.replace("[", "(").replace("]", ")").replace("`", "'")


@app.on_message(filters.command("allrepo"))
async def all_repo_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Please enter a GitHub username.\n\nExample: `/allrepo amritraj78`")

    username = validate_github_username(message.command[1])
    if not username:
        return await message.reply_text("❌ Invalid GitHub username format.")

    try:
        repo_info = await get_all_repository_info(username)

        if not repo_info:
            return await message.reply_text("❌ No public repositories found or user does not exist.")

        chunks = chunk_string(repo_info, 4000)

        for chunk in chunks:
            await message.reply_text(chunk, link_preview_options=LinkPreviewOptions(is_disabled=True))

    except Exception as e:
        LOGGER(__name__).warning(f"Error in /allrepo: {e}")
        await message.reply_text("⚠️ An error occurred while fetching repositories.")


async def get_all_repository_info(username: str) -> str | None:
    url = f"https://api.github.com/users/{username}/repos"
    session = await get_http_session()
    async with session.get(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "AnnieXMusic"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as response:
        if response.status != 200:
            return None
        try:
            data = await response.json()
        except Exception:
            return None

    if not isinstance(data, list) or not data:
        return None

    info_lines = [
        f"🖇 **[{_clean_md(str(repo.get('name', 'repo')))}]({repo.get('html_url', '')})**\n"
        f"⭐ Stars: `{repo.get('stargazers_count', 0)}` | 🍴 Forks: `{repo.get('forks_count', 0)}`\n"
        f"📄 {_clean_md(str(repo.get('description') or 'No description'))}"
        for repo in data[:100]
        if isinstance(repo, dict)
    ]

    profile_link = f"👤 [View GitHub Profile](https://github.com/{username})"
    return f"{profile_link}\n\n" + "\n\n".join(info_lines)
