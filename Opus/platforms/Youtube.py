import asyncio
import os
import re
import glob
import random
import logging
import aiohttp
from typing import Union
import yt_dlp
import config
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

logger = logging.getLogger("YtPlatform")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

_cookie_cache = None

async def download_cookies_from_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    os.makedirs("cookies", exist_ok=True)
                    temp_path = "cookies/cookies.txt"
                    with open(temp_path, 'wb') as f:
                        f.write(await response.read())
                    return temp_path
                else:
                    return None
    except:
        return None

async def cookie_txt_file():
    global _cookie_cache
    if _cookie_cache:
        return _cookie_cache
    remote_url = config.API
    local_path = await download_cookies_from_url(remote_url)
    if local_path:
        _cookie_cache = local_path
        return local_path
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No cookies found")
    cookie_txt_file = random.choice(txt_files)
    _cookie_cache = f"cookies/{str(cookie_txt_file).split('/')[-1]}"
    return _cookie_cache

async def check_file_size(link):
    async def get_format_info(link, cookie_file):
        ydl_opts = {"quiet": True, "cookiefile": cookie_file}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
        return info
    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format and format['filesize']:
                total_size += format['filesize']
        return total_size
    cookie_file = await cookie_txt_file()
    info = await get_format_info(link, cookie_file)
    if not info:
        return None
    formats = info.get('formats', [])
    if not formats:
        return None
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, errorz = await proc.communicate()
    if errorz:
        e = errorz.decode("utf-8")
        if "unavailable videos are hidden" in e.lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.url_regex = re.compile(self.regex)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(self.url_regex.search(link))

    async def url(self, message_1: Message) -> Union[str, None]:
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
        return None

    async def _fetch_video_info(self, link: str, limit: int = 1):
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=limit)
        return (await results.next())["result"]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
            return title, duration_min, duration_sec, thumbnail, vidid
        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            return result["title"]
        return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            return result["duration"]
        return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            return result["thumbnails"][0]["url"].split("?")[0]
        return None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        def video_dl():
            ydl_opts = {
                "format": "(bestvideo[height<=720][width<=1280][ext=mp4])+(bestaudio[ext=m4a]/bestaudio)",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl.download([link])
                return filepath
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, video_dl)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        result = await shell_cmd(cmd)
        try:
            playlist_ids = [key for key in result.split("\n") if key]
            return playlist_ids
        except:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }
            return track_details, result["id"]
        return {}, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        ydl_opts = {"quiet": True, "cookiefile": cookie_file}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            r = ydl.extract_info(link, download=False)
            formats_available = []
            for format in r["formats"]:
                if "dash" in str(format.get("format", "")).lower():
                    continue
                if all(key in format for key in ["format", "filesize", "format_id", "ext", "format_note"]):
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format["filesize"],
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format["format_note"],
                        "yturl": link,
                    })
            return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        result = await self._fetch_video_info(link, limit=10)
        if query_type < len(result):
            r = result[query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        return None, None, None, None

    async def download(self, link: str, mystic, video: Union[bool, str] = None,
                       videoid: Union[bool, str] = None, songaudio: Union[bool, str] = None,
                       songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None,
                       title: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_probe_opts = {"quiet": True, "cookiefile": cookie_file, "nocheckcertificate": True}
            with yt_dlp.YoutubeDL(ydl_probe_opts) as ydl:
                info = ydl.extract_info(link, download=False)
            preferred_exts = ["m4a", "webm", "opus", "mp3", "aac"]
            chosen_format_id, chosen_ext = None, None
            for ext in preferred_exts:
                candidates = [f for f in info.get("formats", [])
                              if f.get("ext") == ext and f.get("acodec") and f.get("acodec") != "none"]
                if candidates:
                    candidates.sort(key=lambda x: (-(x.get("abr") or 0), -(x.get("filesize") or 0)))
                    chosen_format_id = candidates[0].get("format_id") or candidates[0].get("format")
                    chosen_ext = ext
                    break
            if not chosen_format_id:
                audio_only = [f for f in info.get("formats", [])
                              if f.get("acodec") and f.get("acodec") != "none" and not f.get("vcodec")]
                if audio_only:
                    audio_only.sort(key=lambda x: (-(x.get("abr") or 0), -(x.get("filesize") or 0)))
                    chosen_format_id = audio_only[0].get("format_id") or audio_only[0].get("format")
                    chosen_ext = audio_only[0].get("ext")
            format_str = chosen_format_id if chosen_format_id else "bestaudio"
            outtmpl = "downloads/%(id)s." + chosen_ext if chosen_ext else "downloads/%(id)s.%(ext)s"
            ydl_optssx = {
                "format": format_str,
                "outtmpl": outtmpl,
                "geo_bypass": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
                "concurrent_fragment_downloads": 32,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                info_after = ydl.extract_info(link, download=False)
                vid_id = info_after.get("id")
                if vid_id:
                    for p in glob.glob(os.path.join("downloads", f"{vid_id}.*")):
                        if os.path.exists(p):
                            return (p, True)
                ydl.download([link])
            if vid_id:
                matches = glob.glob(os.path.join("downloads", f"{vid_id}.*"))
                if matches:
                    filepath = matches[0]
                    return (filepath, True)
            return (None, False)

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=720][width<=1280][ext=mp4])+(bestaudio[ext=m4a]/bestaudio)",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
                "concurrent_fragment_downloads": 32,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                info = ydl.extract_info(link, download=False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl.download([link])
                return filepath

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                ydl.download([link])
            return f"{fpath}.mp4"

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                ydl.download([link])
            return f"{fpath}.mp3"

        if songvideo:
            return await loop.run_in_executor(None, song_video_dl)
        elif songaudio:
            return await loop.run_in_executor(None, song_audio_dl)
        elif video:
            file_size = await check_file_size(link)
            if not file_size:
                return None
            total_size_mb = file_size / (1024 * 1024)
            if total_size_mb > 1000:
                return None
            return await loop.run_in_executor(None, video_dl)
        else:
            return await loop.run_in_executor(None, audio_dl), True
