import asyncio
import os
import re
import logging
import aiohttp
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from Opus.utils.formatters import time_to_seconds
import urllib.parse

logger = logging.getLogger("JioSaavnAPI")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

class JioSaavnAPI:
    def __init__(self):
        self.base = "https://jiosaavan-rho.vercel.app/api/search/songs?query="
        self.regex = r"(?:jiosaavn\.com|saavn\.com)"  # Optional regex for JioSaavn links
        self.url_regex = re.compile(self.regex)

    async def exists(self, link: str, songid: Union[bool, str] = None):
        """Check if the link is a valid JioSaavn link or query."""
        if songid:
            # If songid is provided, assume it's a valid song ID (not used for API search)
            return True
        return bool(self.url_regex.search(link)) or True  # Treat any string as a potential query

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
        # If no URL, return the message text as a query
        return message_1.text or message_1.caption

    async def _fetch_song_info(self, query: str, limit: int = 1):
        """Fetch song info from JioSaavn API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base}{urllib.parse.quote(query)}"
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch song info: HTTP {response.status}")
                        return []
                    data = await response.json()
                    # Adjust based on actual API response structure
                    # Assuming response is a list of songs or a dict with 'results'
                    results = data.get('results', data) if isinstance(data, dict) else data
                    return results[:limit]
        except Exception as e:
            logger.error(f"Exception while fetching song info: {e}")
            return []

    async def details(self, query: str, songid: Union[bool, str] = None):
        """Get song details (title, duration, thumbnail, ID)."""
        if songid:
            query = songid  # Treat songid as query if provided
        results = await self._fetch_song_info(query)
        for result in results:
            title = result.get('title', 'Unknown Title')
            duration_sec = int(result.get('duration', 0))  # Duration in seconds
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
            thumbnail = result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
            songid = result.get('id', '')
            return title, duration_min, duration_sec, thumbnail, songid
        return None, None, None, None, None

    async def title(self, query: str, songid: Union[bool, str] = None):
        """Get song title."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        for result in results:
            return result.get('title', 'Unknown Title')
        return None

    async def duration(self, query: str, songid: Union[bool, str] = None):
        """Get song duration."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        for result in results:
            duration_sec = int(result.get('duration', 0))
            return f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
        return None

    async def thumbnail(self, query: str, songid: Union[bool, str] = None):
        """Get song thumbnail."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        for result in results:
            return result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
        return None

    async def track(self, query: str, songid: Union[bool, str] = None):
        """Get track details as a dictionary."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        for result in results:
            duration_sec = int(result.get('duration', 0))
            track_details = {
                "title": result.get('title', 'Unknown Title'),
                "link": result.get('url', ''),  # JioSaavn song URL
                "vidid": result.get('id', ''),  # Using 'vidid' to maintain compatibility
                "duration_min": f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00",
                "thumb": result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', ''),
            }
            return track_details, result.get('id', '')
        return {}, None

    async def formats(self, query: str, songid: Union[bool, str] = None):
        """Get available formats (simplified for JioSaavn)."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        formats_available = []
        for result in results:
            # JioSaavn typically provides a single audio format (e.g., MP3)
            media_url = result.get('media_url', '')
            if media_url:
                formats_available.append({
                    "format": "audio/mp3",
                    "filesize": None,  # JioSaavn API may not provide filesize
                    "format_id": "mp3",
                    "ext": "mp3",
                    "format_note": "320kbps",  # Assume high quality
                    "yturl": result.get('url', query),  # Use song URL or query
                })
        return formats_available, query

    async def download(
        self,
        query: str,
        mystic,
        video: Union[bool, str] = None,
        songid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """Download song audio from JioSaavn."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query)
        if not results:
            logger.error("No results found for download.")
            return None

        result = results[0]
        media_url = result.get('media_url', '')
        if not media_url:
            logger.error("No media URL found for download.")
            return None

        song_id = result.get('id', 'unknown')
        title = title or result.get('title', 'unknown_song').replace(' ', '_')
        filepath = f"downloads/{title}.mp3"

        async def download_audio():
            """Download audio file from media_url."""
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

    async def playlist(self, query: str, limit: int, user_id: int, songid: Union[bool, str] = None):
        """Fetch playlist (not supported by JioSaavn API in this context)."""
        logger.warning("Playlist functionality not implemented for JioSaavn API.")
        return []

    async def slider(self, query: str, query_type: int, songid: Union[bool, str] = None):
        """Get song details for a specific result index (slider)."""
        if songid:
            query = songid
        results = await self._fetch_song_info(query, limit=10)
        if query_type < len(results):
            result = results[query_type]
            title = result.get('title', 'Unknown Title')
            duration_sec = int(result.get('duration', 0))
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
            thumbnail = result.get('image', [{}])[-1].get('url', '') if isinstance(result.get('image'), list) else result.get('image', '')
            songid = result.get('id', '')
            return title, duration_min, thumbnail, songid
        return None, None, None, None

    async def check_file_size(self, query: str, songid: Union[bool, str] = None):
        """Check file size (not supported as JioSaavn API may not provide it)."""
        logger.warning("File size check not supported for JioSaavn API.")
        return None
