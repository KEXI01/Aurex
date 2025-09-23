import asyncio
import os
import re
import json
from typing import Union, Tuple, Optional
import aiohttp
import random
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

API_URL = "https://ar-api-iauy.onrender.com/mp3youtube"

def cookie_txt_file():
    """Select a random cookie file from the cookies directory."""
    cookie_dir = f"{os.getcwd()}/cookies"
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        raise FileNotFoundError("No cookie files found in cookies directory")
    return os.path.join(cookie_dir, random.choice(cookies_files))

async def download_song(link: str, download_mode: str = "audio") -> Optional[str]:
    """
    Download a YouTube video or audio using the single API.
    Args:
        link (str): YouTube video URL.
        download_mode (str): "audio" for MP3, "video" for MP4.
    Returns:
        Optional[str]: Path to the downloaded file or None if failed.
    """
    video_id = link.split('v=')[-1].split('&')[0]
    download_folder = "downloads"
    file_extension = "mp3" if download_mode == "audio" else "mp4"
    file_path = os.path.join(download_folder, f"{video_id}.{file_extension}")

    if os.path.exists(file_path):
        return file_path

    os.makedirs(download_folder, exist_ok=True)

    # Construct API URL with format parameter
    api_url = f"{API_URL}?url=https://www.youtube.com/watch?v={video_id}&format={file_extension}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"API request failed with status {response.status}")
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                return file_path
        except Exception as e:
            print(f"[API Download Error] Failed to download {download_mode}: {e}")
            return None

async def check_file_size(link: str) -> Optional[int]:
    """
    Check the total file size of a YouTube video using yt-dlp.
    Args:
        link (str): YouTube video URL.
    Returns:
        Optional[int]: Total file size in bytes or None if failed.
    """
    async def get_format_info(link: str) -> Optional[dict]:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"[yt-dlp Error] {stderr.decode()}")
            return None
        return json.loads(stdout.decode())

    def parse_size(formats: list) -> int:
        return sum(format.get('filesize', 0) for format in formats if 'filesize' in format)

    info = await get_format_info(link)
    if not info:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("[yt-dlp Error] No formats found")
        return None
    
    return parse_size(formats)

async def shell_cmd(cmd: str) -> str:
    """
    Execute a shell command and return its output.
    Args:
        cmd (str): Command to execute.
    Returns:
        str: Command output or error message.
    """
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, error = await proc.communicate()
    if error:
        error_text = error.decode("utf-8").lower()
        if "unavailable videos are hidden" in error_text:
            return out.decode("utf-8")
        return error_text
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def _extract_video_id(self, link: str, videoid: Union[bool, str] = None) -> str:
        """Extract video ID from link or use provided videoid."""
        if videoid and isinstance(videoid, str):
            return videoid
        return link.split('v=')[-1].split('&')[0] if '&' in link else link

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result.get("duration", "0:00")
            duration_sec = int(time_to_seconds(duration_min))
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            print(f"[Details Error] Failed to fetch video details: {e}")
            return "", "0:00", 0, "", ""

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result["title"]
        except Exception as e:
            print(f"[Title Error] Failed to fetch video title: {e}")
            return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result.get("duration", "0:00")
        except Exception as e:
            print(f"[Duration Error] Failed to fetch video duration: {e}")
            return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result["thumbnails"][0]["url"].split("?")[0]
        except Exception as e:
            print(f"[Thumbnail Error] Failed to fetch video thumbnail: {e}")
            return ""

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> list:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        playlist = await shell_cmd(cmd)
        try:
            result = [id for id in playlist.split("\n") if id]
            return result
        except Exception as e:
            print(f"[Playlist Error] Failed to parse playlist: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[dict, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result.get("duration", "0:00"),
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }
            return track_details, result["id"]
        except Exception as e:
            print(f"[Track Error] Failed to fetch track details: {e}")
            return {}, ""

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            try:
                info = ydl.extract_info(link, download=False)
                for format in info["formats"]:
                    if "dash" in format.get("format", "").lower():
                        continue
                    try:
                        formats_available.append({
                            "format": format["format"],
                            "filesize": format.get("filesize"),
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format.get("format_note", ""),
                            "yturl": link,
                        })
                    except KeyError:
                        continue
                return formats_available, link
            except Exception as e:
                print(f"[Formats Error] Failed to fetch formats: {e}")
                return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None) -> Tuple[str, str, str, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=10)
            result = (await results.next())["result"][query_type]
            return (
                result["title"],
                result.get("duration", "0:00"),
                result["thumbnails"][0]["url"].split("?")[0],
                result["id"],
            )
        except Exception as e:
            print(f"[Slider Error] Failed to fetch slider details: {e}")
            return "", "0:00", "", ""

    async def download(
        self,
        link: str,
        mystic,  # Context object (e.g., Pyrogram message)
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Tuple[Optional[str], bool]:
        if videoid:
            link = self.base + link

        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"{fpath}.mp4"

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"{fpath[:-7]}.mp3"

        # For video streaming (return streaming URL for VC)
        if video:
            if await is_on_off(1):
                downloaded_file = await download_song(link, "video")
                if downloaded_file:
                    return downloaded_file, True
            # Use yt-dlp to get streaming URL for video (critical for VC)
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                downloaded_file = stdout.decode().split("\n")[0]
                direct = False  # Indicates streaming URL
            else:
                file_size = await check_file_size(link)
                if not file_size:
                    print("[Download Error] Could not determine file size")
                    return None, False
                total_size_mb = file_size / (1024 * 1024)
                if total_size_mb > 250:
                    print(f"[Download Error] File size {total_size_mb:.2f} MB exceeds 250MB limit")
                    return None, False
                direct = True  # Indicates local file
                downloaded_file = await loop.run_in_executor(None, video_dl)
            return downloaded_file, direct
        # For audio (songaudio, songvideo, or default audio)
        else:
            if songvideo or songaudio:
                download_mode = "video" if songvideo else "audio"
                downloaded_file = await download_song(link, download_mode)
                if downloaded_file:
                    return downloaded_file, True
                downloaded_file = await loop.run_in_executor(None, song_video_dl if songvideo else song_audio_dl)
                return downloaded_file, True
            else:
                downloaded_file = await download_song(link, "audio")
                if downloaded_file:
                    return downloaded_file, True
                downloaded_file = await loop.run_in_executor(None, audio_dl)
                return downloaded_file, True
