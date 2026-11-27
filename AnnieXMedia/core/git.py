# Authored By Certified Coders © 2025
import asyncio
import shlex
from typing import Tuple
from urllib.parse import quote, urlsplit, urlunsplit

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config
from AnnieXMedia.core.security import redact_secrets

from ..logging import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.run(install_requirements())


def _build_authenticated_url(repo_url: str, token: str) -> str:
    """Build an authenticated HTTPS clone/fetch URL for any Git host without assuming .com."""
    parts = urlsplit((repo_url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return repo_url
    host = parts.netloc.split("@")[-1]
    owner_hint = (parts.path.strip("/").split("/") or ["git"])[0] or "git"
    cred = f"{quote(owner_hint, safe='')}:{quote(token, safe='')}"
    return urlunsplit((parts.scheme, f"{cred}@{host}", parts.path, parts.query, parts.fragment))


def git():
    clean_repo = (config.UPSTREAM_REPO or "").strip()
    auth_repo = (
        _build_authenticated_url(clean_repo, config.GIT_TOKEN)
        if config.GIT_TOKEN and clean_repo
        else clean_repo
    )
    try:
        Repo()
        LOGGER(__name__).info("Git Client Found [VPS DEPLOYER]")
    except GitCommandError:
        LOGGER(__name__).info("Invalid Git Command")
    except InvalidGitRepositoryError:
        try:
            repo = Repo.init()
            origin = (
                repo.remote("origin")
                if "origin" in repo.remotes
                else repo.create_remote("origin", auth_repo)
            )
            try:
                origin.set_url(auth_repo)
                origin.fetch()
                if config.UPSTREAM_BRANCH not in repo.heads:
                    repo.create_head(
                        config.UPSTREAM_BRANCH,
                        origin.refs[config.UPSTREAM_BRANCH],
                    )
                repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(
                    origin.refs[config.UPSTREAM_BRANCH]
                )
                repo.heads[config.UPSTREAM_BRANCH].checkout(True)
                try:
                    origin.pull(config.UPSTREAM_BRANCH)
                except GitCommandError:
                    repo.git.reset("--hard", "FETCH_HEAD")
            finally:
                # Always strip credentials from .git/config once sync finishes
                try:
                    origin.set_url(clean_repo)
                except Exception:
                    pass
            LOGGER(__name__).info("Fetching updates from upstream repository...")
        except Exception as e:
            LOGGER(__name__).warning(f"Git auto-sync skipped: {redact_secrets(str(e))}")
