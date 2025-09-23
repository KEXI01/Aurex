import asyncio
import os
import re
import json
import random
from typing import Union, Tuple, Optional
import aiohttp
from youtubesearchpython.__future__ import VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import yt_dlp
from functools import lru_cache

# Configuration
API_URLS = [
    "https://ar-api-iauy.onrender.com/mp3youtube",  # Faster API prioritized
    "https://ashlynn-repo.vercel.app/cobolt"
]
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_MB = 250
DEFAULT_TIMEOUT = 15  # Reduced timeout for faster response

# Cache for metadata to avoid redundant queries
@lru_cache(maxsize=100)
def cached_video_metadata(video_id: str) -> tuple:
    """Cache video metadata to reduce API calls."""
    results = VideosSearch(f"https://www.youtube.com/watch?v={video_id}", limit=1)
    result = results.next()["result"][0]
    return (
        result["title"],
        result["duration"] or "0:00",
        int(time_to_seconds(result["duration"] or "0:00")),
        result["thumbnails"][0]["url"].split("?")[0],
        result["id"]
    )

def time_to_seconds(duration: str) -> int:
    """Convert duration string (MM:SS or HH:MM:SS) to seconds."""
    if not duration or duration == "None":
        return 0
    parts = list(map(int, duration.split(":")))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0

def get_cookie_file() -> str:
    """Select a random cookie file from the cookies directory."""
    cookie_dir = os.path.join(os.getcwd(), "cookies")
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        raise FileNotFoundError("No cookie files found in cookies directory")
    return os.path.join(cookie_dir, random.choice(cookies_files))

async def download_file(url: str, path: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """Download a file from a URL and save it to the specified path."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return False
                with open(path, 'wb') as f:
                    f.write(await response.read())
                return True
        except Exception as e:
            print(f"[Download Error] {e}")
            return False

async def download_song(link: str, download_mode: str = "audio") -> Optional[str]:
    """Download a song or video using prioritized APIs with fallback to yt-dlp."""
    video_id = link.split('v=')[-1].split('&')[0]
    file_extension = "mp3" if download_mode == "audio" else "mp4"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{file_extension}")

    if os.path.exists(file_path):
        return file_path

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Try APIs in order of priority
    for api_url in API_URLS:
        try:
            if api_url.endswith("arytmp3"):
                song_url = f"{api_url}?direct&id={video_id}"
            else:
                song_url = f"{api_url}?url=https://www.youtube.com/watch?v={video_id}&downloadMode={download_mode}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(song_url, timeout=DEFAULT_TIMEOUT) as response:
                    if response.status != 200:
                        continue
                    if api_url.endswith("arytmp3"):
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                        return file_path
                    else:
                        data = await response.json()
                        if data.get("status") != 200 or data.get("successful") != "success":
                            continue
                        download_url = data.get("data", {}).get("url")
                        if not download_url:
                            continue
                        if await download_file(download_url, file_path):
                            return file_path
        except Exception as e:
            print(f"[API {api_url} failed] {e}")
            continue

    return None

async def check_file_size(link: str) -> Optional[int]:
    """Check the file size of a video using yt-dlp."""
    cmd = ["yt-dlp", "--cookies", get_cookie_file(), "-J", link]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"[yt-dlp Error] {stderr.decode()}")
        return None
    
    try:
        info = json.loads(stdout.decode())
        total_size = sum(f["filesize"] for f in info.get("formats", []) if "filesize" in f)
        return total_size
    except Exception as e:
        print(f"[File Size Parse Error] {e}")
        return None

async def shell_cmd(cmd: str) -> str:
    """Execute a shell command and return output."""
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return err.decode() if err else out.decode()

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        """Check if a YouTube link is valid."""
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        """Extract a URL from a message or its reply."""
        messages = [message, message.reply_to_message] if message.reply_to_message else [message]
        for msg in messages:
            if not msg:
                continue
            entities = msg.entities or msg.caption_entities
            if entities:
                for entity in entities:
                    if entity.type == MessageEntityType.URL:
                        return (msg.text or msg.caption)[entity.offset:entity.offset + entity.length]
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        """Get video details using cached metadata."""
        video_id = link.split('v=')[-1].split('&')[0] if videoid else link
        return cached_video_metadata(video_id)

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        """Get video title."""
        return (await self.details(link, videoid))[0]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        """Get video duration."""
        return (await self.details(link, videoid))[1]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        """Get video thumbnail."""
        return (await self.details(link, videoid))[3]

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        """Get video stream URL."""
        if videoid:
            link = self.base + link
        cmd = [
            "yt-dlp", "--cookies", get_cookie_file(), "-g", "-f",
            "best[height<=?720][width<=?1280]", link
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> list:
        """Get playlist video IDs."""
        if videoid:
            link = self.listbase + link
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {get_cookie_file()} --playlist-end {limit} --skip-download {link}"
        result = (await shell_cmd(cmd)).split("\n")
        return [vid for vid in result if vid]

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[dict, str]:
        """Get track details."""
        title, duration_min, _, thumbnail, vidid = await self.details(link, videoid)
        return {
            "title": title,
            "link": link if videoid else self.base + link,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail
        }, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        """Get available video formats."""
        if videoid:
            link = self.base + link
        ydl_opts = {"quiet": True, "cookiefile": get_cookie_file()}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            formats_available = [
                {
                    "format": f["format"],
                    "filesize": f["filesize"],
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "format_note": f["format_note"],
                    "yturl": link
                }
                for f in info["formats"]
                if "dash" not in f["format"].lower() and all(k in f for k in ["format", "filesize", "format_id", "ext", "format_note"])
            ]
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None) -> Tuple[str, str, str, str]:
        """Get video details for a specific query type."""
        if videoid:
            link = self.base + link
        results = (await VideosSearch(link, limit=10).next())["result"]
        result = results[query_type]
        return (
            result["title"],
            result["duration"] or "0:00",
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"]
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None
    ) -> Tuple[Optional[str], bool]:
        """Download a video or audio file with optimized logic."""
        if videoid:
            link = self.base + link

        async def ytdl_download(mode: str, custom_format: str = None, custom_title: str = None) -> str:
            ydl_opts = {
                "format": custom_format or ("bestaudio/best" if mode == "audio" else "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])"),
                "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s" if not custom_title else f"{DOWNLOAD_DIR}/{custom_title}.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": get_cookie_file(),
                "no_warnings": True
            }
            if mode == "audio" and custom_format:
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }]
                ydl_opts["prefer_ffmpeg"] = True
                ydl_opts["merge_output_format"] = "mp3"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                file_path = ydl.prepare_filename(info)
                if os.path.exists(file_path):
                    return file_path
                ydl.download([link])
                return file_path

        # Main download logic
        if songaudio or songvideo:
            download_mode = "video" if songvideo else "audio"
            downloaded_file = await download_song(link, download_mode)
            if downloaded_file:
                return downloaded_file, True
            # Fallback to yt-dlp
            format_str = f"{format_id}+140" if songvideo else format_id
            downloaded_file = await ytdl_download(download_mode, format_str, title)
            return downloaded_file, True

        elif video:
            downloaded_file = await download_song(link, "video")
            if downloaded_file:
                return downloaded_file, True
            file_size = await check_file_size(link)
            if not file_size:
                return None, False
            if file_size / (1024 * 1024) > MAX_FILE_SIZE_MB:
                print(f"File size exceeds {MAX_FILE_SIZE_MB}MB limit")
                return None, False
            downloaded_file = await ytdl_download("video")
            return downloaded_file, True

        else:
            downloaded_file = await download_song(link, "audio")
            if downloaded_file:
                return downloaded_file, True
            downloaded_file = await ytdl_download("audio")
            return downloaded_file, True
