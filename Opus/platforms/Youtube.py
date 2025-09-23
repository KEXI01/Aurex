import asyncio
import os
import re
import json
from typing import Union, Tuple, Optional
import requests
import random
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds
import aiohttp

API_URL1 = "https://ashlynn-repo.vercel.app/cobolt"
API_URL2 = "https://ar-api-iauy.onrender.com/mp3youtube"

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

async def download_song(link: str, download_mode: str = "audio"):
    video_id = link.split('v=')[-1].split('&')[0]
    download_folder = "downloads"
    file_extension = "mp3" if download_mode == "audio" else "mp4"
    file_path = os.path.join(download_folder, f"{video_id}.{file_extension}")

    if os.path.exists(file_path):
        return file_path

    os.makedirs(download_folder, exist_ok=True)

    async def download_file(url, path):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=25) as response:
                    if response.status != 200:
                        raise Exception(f"File download failed with status {response.status}")
                    content = await response.read()
                    with open(path, 'wb') as f:
                        f.write(content)
                    return True
            except Exception as e:
                print(f"[File Download Error] {e}")
                return False

    try:
        song_url2 = f"{API_URL2}?direct&id={video_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(song_url2, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"API 2 request failed with status {response.status}")
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                return file_path
    except Exception as e:
        print(f"[API 2 failed] {e}")

    try:
        song_url1 = f"{API_URL1}?url=https://www.youtube.com/watch?v={video_id}&downloadMode={download_mode}"
        async with aiohttp.ClientSession() as session:
            async with session.get(song_url1, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"API 1 request failed with status {response.status}")
                data = await response.json()
                if data.get("status") != 200 or data.get("successful") != "success":
                    raise Exception(f"API 1 error: {data.get('message', 'Unknown error')}")
                download_url = data.get("data", {}).get("url")
                if not download_url:
                    raise Exception("API 1 response missing download URL")
                if await download_file(download_url, file_path):
                    return file_path
    except Exception as e:
        print(f"[API 1 as a fallback failed] {e}")

    return None

async def check_file_size(link):
    async def get_format_info(link):
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
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def _extract_video_id(self, link: str, videoid: Union[bool, str] = None) -> str:
        """Extract video ID from link or use provided videoid."""
        if videoid:
            return videoid if isinstance(videoid, str) else link
        return link.split('v=')[-1].split('&')[0] if '&' in link else link

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset:offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result["duration"] or "0:00"
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
            return result["duration"] or "0:00"
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
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[dict, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result["duration"] or "0:00"
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            track_details = {
                "title": title,
                "link": yturl,
                "vidid": vidid,
                "duration_min": duration_min,
                "thumb": thumbnail,
            }
            return track_details, vidid
        except Exception as e:
            print(f"[Track Error] Failed to fetch track details: {e}")
            return {}, ""

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ) -> Tuple[str, str, str, str]:
        video_id = self._extract_video_id(link, videoid)
        link = self.base + video_id
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result")
            title = result[query_type]["title"]
            duration_min = result[query_type]["duration"] or "0:00"
            vidid = result[query_type]["id"]
            thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
            return title, duration_min, thumbnail, vidid
        except Exception as e:
            print(f"[Slider Error] Failed to fetch slider details: {e}")
            return "", "0:00", "", ""

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
    ) -> Tuple[str, bool]:
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
            info = x.extract_info(link, False)
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
            info = x.extract_info(link, False)
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

        if songvideo or songaudio:
            download_mode = "video" if songvideo else "audio"
            downloaded_file = await download_song(link, download_mode)
            if downloaded_file:
                return downloaded_file, True
            if songvideo:
                downloaded_file = await loop.run_in_executor(None, song_video_dl)
            else:
                downloaded_file = await loop.run_in_executor(None, song_audio_dl)
            return downloaded_file, True
        elif video:
            if await is_on_off(1):
                downloaded_file = await download_song(link, "video")
                if downloaded_file:
                    return downloaded_file, True
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                f"{link}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                downloaded_file = stdout.decode().split("\n")[0]
                direct = False
            else:
                file_size = await check_file_size(link)
                if not file_size:
                    print("None file Size")
                    return None, False
                total_size_mb = file_size / (1024 * 1024)
                if total_size_mb > 250:
                    print(f"File size {total_size_mb:.2f} MB exceeds the 100MB limit.")
                    return None, False
                direct = True
                downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            downloaded_file = await download_song(link, "audio")
            if downloaded_file:
                return downloaded_file, True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        return downloaded_file, True
