import asyncio
import os
import re
import glob
import random
import logging
import aiohttp
from typing import Union
import urllib.parse
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from Opus.utils.formatters import time_to_seconds

logger = logging.getLogger("YouTubeAPI")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

_cookie_cache = None

async def download_cookies_from_url(url):
    # Placeholder: JioSaavn API likely doesn't need cookies, but kept for compatibility
    logger.warning("Cookie download not required for JioSaavn API.")
    return None

async def cookie_txt_file():
    # Placeholder: Return None as cookies are not needed
    global _cookie_cache
    if _cookie_cache:
        return _cookie_cache
    logger.warning("No cookies required for JioSaavn API.")
    _cookie_cache = None
    return None

async def check_file_size(link):
    # Placeholder: JioSaavn API may not provide file size
    logger.warning("File size check not supported for JioSaavn API.")
    return None

async def shell_cmd(cmd):
    # Placeholder: Not needed for JioSaavn, but kept for compatibility
    logger.warning("Shell command not used for JioSaavn API.")
    return ""

class YouTubeAPI:
    def __init__(self):
        self.base = "https://jiosaavan-rho.vercel.app/api/search/songs?query="
        self.regex = r"(?:jiosaavn\.com|saavn\.com)"  # Optional regex for JioSaavn links
        self.listbase = "https://jiosaavn.com/playlist?list="  # Placeholder for playlists
        self.url_regex = re.compile(self.regex)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        """Check if the link is a valid JioSaavn link or query."""
        if videoid:
            return True  # Treat videoid as a valid song ID
        return bool(self.url_regex.search(link)) or True  # Treat any string as a query

    async def url(self, message_1: Message) -> Union[str, None]:
        """Extract URL or query from message."""
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return (message.text or message.caption)[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return message_1.text or message_1.caption  # Return text as query if no URL

    async def _fetch_video_info(self, link: str, limit: int = 1):
        """Fetch song info from JioSaavn API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base}{urllib.parse.quote(link)}"
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch song info: HTTP {response.status}")
                        return []
                    data = await response.json()
                    results = data.get('results', data) if isinstance(data, dict) else data
                    return results[:limit]
        except Exception as e:
            logger.error(f"Exception while fetching song info: {e}")
            return []

    async def details(self, link: str, videoid: Union[bool, str] = None):
        """Get song details (title, duration, thumbnail, ID)."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            title = result.get('title', 'Unknown Title')
            duration_sec = int(result.get('duration', 0))
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
            thumbnail = result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
            vidid = result.get('id', '')
            return title, duration_min, duration_sec, thumbnail, vidid
        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        """Get song title."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            return result.get('title', 'Unknown Title')
        return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        """Get song duration."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            duration_sec = int(result.get('duration', 0))
            return f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
        return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        """Get song thumbnail."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            return result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
        return None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Download audio (video not supported)."""
        if videoid:
            link = videoid
        logger.warning("Video download not supported; downloading audio instead.")
        return await self.download(link, None, video=False)

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None):
        """Fetch playlist (not supported)."""
        logger.warning("Playlist functionality not implemented for JioSaavn API.")
        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        """Get track details as a dictionary."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            duration_sec = int(result.get('duration', 0))
            track_details = {
                "title": result.get('title', 'Unknown Title'),
                "link": result.get('url', link),
                "vidid": result.get('id', ''),
                "duration_min": f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00",
                "thumb": result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', ''),
            }
            return track_details, result.get('id', '')
        return {}, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        """Get available formats (simplified for JioSaavn)."""
        if videoid:
            link = videoid
        for result in await self._fetch_video_info(link):
            formats_available = [{
                "format": "audio/mp3",
                "filesize": None,
                "format_id": "mp3",
                "ext": "mp3",
                "format_note": "320kbps",
                "yturl": result.get('url', link),
            }]
            return formats_available, link
        return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        """Get song details for a specific result index."""
        if videoid:
            link = videoid
        results = await self._fetch_video_info(link, limit=10)
        if query_type < len(results):
            result = results[query_type]
            title = result.get('title', 'Unknown Title')
            duration_sec = int(result.get('duration', 0))
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
            thumbnail = result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
            vidid = result.get('id', '')
            return title, duration_min, thumbnail, vidid
        return None, None, None, None

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """Download song audio from JioSaavn."""
        if videoid:
            link = videoid
        if video or songvideo:
            logger.warning("Video download not supported; downloading audio instead.")

        results = await self._fetch_video_info(link)
        if not results:
            logger.error("No results found for download.")
            return None, False

        result = results[0]
        media_url = result.get('media_url', '')
        if not media_url:
            logger.error("No media URL found for download.")
            return None, False

        song_id = result.get('id', 'unknown')
        title = title or result.get('title', 'unknown_song').replace(' ', '_')
        filepath = f"downloads/{title}.mp3"

        async def download_audio():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(media_url) as response:
                        if response.status != 200:
                            logger.error(f"Failed to download audio: HTTP {response.status}")
                            return None
                        os.makedirs("downloads", exist_ok=True)
                        with open(filepath, 'wb') as f:
                            f.write(await response.read())
                        logger.info(f"Completed audio download: {filepath}")
                        return filepath
            except Exception as e:
                logger.error(f"Exception while downloading audio: {e}")
                return None

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, download_audio)
        return result, True if result else False
