# Authored By Certified Coders © 2025
import asyncio
import re
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.aio import VideosSearch

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^https:\/\/open\.spotify\.com\/.+"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        self._lock = asyncio.Lock()
        if self.client_id and self.client_secret:
            self.client_credentials_manager = SpotifyClientCredentials(
                self.client_id, self.client_secret, requests_timeout=10
            )
            self.spotify = spotipy.Spotify(
                client_credentials_manager=self.client_credentials_manager,
                requests_timeout=10,
            )
        else:
            self.spotify = None

    async def valid(self, link: Optional[str]) -> bool:
        return bool(re.search(self.regex, link or ""))

    async def _call(self, fn, *args):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        async with self._lock:
            return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=15.0)

    def _format_artists(self, name: str, artists: list) -> str:
        info = str(name or "")
        for artist in artists or []:
            if not isinstance(artist, dict):
                continue
            aname = str(artist.get("name") or "")
            if aname and "Various Artists" not in aname:
                info += f" {aname}"
        return info.strip()

    async def track(self, link: str):
        track = await self._call(self.spotify.track, link)
        if not isinstance(track, dict) or not track.get("name"):
            return None, None
        info = self._format_artists(track.get("name", ""), track.get("artists") or [])
        data = await VideosSearch(info, limit=1).next()
        results = data.get("result") or []
        if not results:
            return None, None
        r = results[0]
        thumbs = r.get("thumbnails") or []
        thumb_url = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
        track_details = {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "vidid": r.get("id", ""),
            "duration_min": r.get("duration"),
            "thumb": thumb_url,
        }
        return track_details, track_details["vidid"]

    async def playlist(self, url: str):
        playlist = await self._call(self.spotify.playlist, url)
        if not isinstance(playlist, dict):
            return [], ""
        playlist_id = str(playlist.get("id") or "")
        results = []
        items = (playlist.get("tracks") or {}).get("items") or []
        for item in items:
            music_track = item.get("track") if isinstance(item, dict) else None
            if not isinstance(music_track, dict) or not music_track.get("name"):
                continue
            results.append(self._format_artists(music_track.get("name", ""), music_track.get("artists") or []))
        return results, playlist_id

    async def album(self, url: str):
        album = await self._call(self.spotify.album, url)
        if not isinstance(album, dict):
            return [], ""
        album_id = str(album.get("id") or "")
        results = []
        items = (album.get("tracks") or {}).get("items") or []
        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            results.append(self._format_artists(item.get("name", ""), item.get("artists") or []))
        return results, album_id

    async def artist(self, url: str):
        artistinfo = await self._call(self.spotify.artist, url)
        if not isinstance(artistinfo, dict):
            return [], ""
        artist_id = str(artistinfo.get("id") or "")
        results = []
        artisttoptracks = await self._call(self.spotify.artist_top_tracks, url)
        for item in (artisttoptracks or {}).get("tracks") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            results.append(self._format_artists(item.get("name", ""), item.get("artists") or []))
        return results, artist_id
