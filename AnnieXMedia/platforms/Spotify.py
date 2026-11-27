# Authored By Certified Coders © 2025
import asyncio
import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.aio import VideosSearch

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^https:\/\/open\.spotify\.com\/.+"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        if self.client_id and self.client_secret:
            self.client_credentials_manager = SpotifyClientCredentials(
                self.client_id, self.client_secret
            )
            self.spotify = spotipy.Spotify(
                client_credentials_manager=self.client_credentials_manager
            )
        else:
            self.spotify = None

    async def valid(self, link: str) -> bool:
        return bool(re.search(self.regex, link or ""))

    async def track(self, link: str):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        track = await asyncio.to_thread(self.spotify.track, link)
        info = track["name"]
        for artist in track.get("artists", []):
            fetched = f' {artist["name"]}'
            if "Various Artists" not in fetched:
                info += fetched
        results = VideosSearch(info, limit=1)
        data = await results.next()
        if not data.get("result"):
            return None, None
        r = data["result"][0]
        thumbs = r.get("thumbnails", [])
        thumb_url = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
        track_details = {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "vidid": r.get("id", ""),
            "duration_min": r.get("duration"),
            "thumb": thumb_url,
        }
        return track_details, track_details["vidid"]

    async def playlist(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        playlist = await asyncio.to_thread(self.spotify.playlist, url)
        playlist_id = playlist["id"]
        results = []
        for item in playlist.get("tracks", {}).get("items", []):
            if not item or not item.get("track"):
                continue
            music_track = item["track"]
            info = music_track["name"]
            for artist in music_track.get("artists", []):
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, playlist_id

    async def album(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        album = await asyncio.to_thread(self.spotify.album, url)
        album_id = album["id"]
        results = []
        for item in album.get("tracks", {}).get("items", []):
            if not item:
                continue
            info = item.get("name", "")
            for artist in item.get("artists", []):
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, album_id

    async def artist(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        artistinfo = await asyncio.to_thread(self.spotify.artist, url)
        artist_id = artistinfo["id"]
        results = []
        artisttoptracks = await asyncio.to_thread(self.spotify.artist_top_tracks, url)
        for item in artisttoptracks.get("tracks", []):
            if not item:
                continue
            info = item.get("name", "")
            for artist in item.get("artists", []):
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, artist_id
