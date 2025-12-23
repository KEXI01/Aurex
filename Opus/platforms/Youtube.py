import os
import re
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
import httpx
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from youtubesearchpython.__future__ import VideosSearch

from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds, seconds_to_min
from Opus.utils.downloader import (
    download_audio,
    download_video,
    download_song_audio,
    download_song_video,
)

COOKIE_PATH = "Opus/assets/cookies.txt"


def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return COOKIE_PATH
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    return await proc.communicate()


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(youtube\.com|youtu\.be)")

    def _extract_id(self, link: str) -> Optional[str]:
        if "watch?v=" in link:
            return link.split("watch?v=")[-1].split("&")[0]
        if "youtu.be/" in link:
            return link.split("youtu.be/")[-1].split("?")[0]
        if "/live/" in link:
            return link.split("/live/")[-1].split("?")[0]
        if "/shorts/" in link:
            return link.split("/shorts/")[-1].split("?")[0]
        return None

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            return self.base_url + videoid.strip()
        vid = self._extract_id(link)
        if vid:
            return self.base_url + vid
        return link.split("&")[0]

    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def _dump(self, link: str) -> Optional[Dict]:
        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "--dump-json",
            "--no-playlist",
            link,
        )
        if not stdout:
            return None
        try:
            return json.loads(stdout.decode())
        except Exception:
            return None

    async def is_live(self, link: str) -> bool:
        info = await self._dump(self._prepare_link(link))
        if not info:
            return False
        if info.get("is_live"):
            return True
        if info.get("live_status") == "is_live":
            return True
        return False

    async def _fetch_video_info(self, query: str) -> Optional[Dict]:
        prepared = self._prepare_link(query)
        info = await self._dump(prepared)
        if info:
            info["webpage_url"] = info.get("webpage_url", prepared)
            if "thumbnails" not in info:
                if info.get("thumbnail"):
                    info["thumbnails"] = [{"url": info["thumbnail"]}]
            return info
        try:
            data = await VideosSearch(query, limit=1).next()
            result = data.get("result", [])
            if not result:
                return None
            info = result[0]
            info["webpage_url"] = self.base_url + info.get("id", "")
            if "thumbnails" not in info:
                info["thumbnails"] = [{"url": info.get("thumbnail", "")}]
            return info
        except Exception:
            return None

    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Union[str, int, None], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        is_live = bool(info.get("is_live") or info.get("live_status") == "is_live")
        seconds = info.get("duration")
        duration = seconds if is_live or seconds is None else seconds_to_min(seconds)
        ds = int(seconds) if isinstance(seconds, int) else 0
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[0].get("url", "")
        ).split("?")[0]
        return info.get("title", ""), duration, ds, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None):
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            return None
        if info.get("is_live") or info.get("live_status") == "is_live":
            return info.get("duration")
        if isinstance(info.get("duration"), int):
            return seconds_to_min(info["duration"])
        return info.get("duration")

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            return ""
        return (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[0].get("url", "")
        ).split("?")[0]

    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "--no-playlist",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Track not found")
        is_live = bool(info.get("is_live") or info.get("live_status") == "is_live")
        seconds = info.get("duration")
        duration = seconds if is_live or seconds is None else seconds_to_min(seconds)
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[0].get("url", "")
        ).split("?")[0]
        return (
            {
                "title": info.get("title", ""),
                "link": info.get("webpage_url"),
                "vidid": info.get("id", ""),
                "duration_min": duration,
                "thumb": thumb,
            },
            info.get("id", ""),
        )

    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        opts = {"quiet": True}
        cf = _cookiefile_path()
        if cf:
            opts["cookiefile"] = cf
        out: List[Dict] = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            for fmt in info.get("formats", []):
                if "dash" in str(fmt.get("format", "")).lower():
                    continue
                if not any(k in fmt for k in ("filesize", "filesize_approx")):
                    continue
                if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                    continue
                size = fmt.get("filesize") or fmt.get("filesize_approx")
                if not size:
                    continue
                out.append(
                    {
                        "format": fmt["format"],
                        "filesize": size,
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    }
                )
        return out, link

    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ):
        link = self._prepare_link(link, videoid)

        if songvideo:
            p = await download_song_video(link, format_id, title)
            return (p, True) if p else (None, None)

        if songaudio:
            p = await download_song_audio(link, format_id, title)
            return (p, True) if p else (None, None)

        if video:
            if await self.is_live(link):
                status, stream = await self.video(link)
                if status == 1:
                    return stream, None
                raise ValueError("FAILED TO STREAM YOUTUBE LIVE STREAM")
            p = await download_video(link, quality=360)
            return (p, True) if p else (None, None)

        p = await download_audio(link)
        return (p, True) if p else (None, None)
