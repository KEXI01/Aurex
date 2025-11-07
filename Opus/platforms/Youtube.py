import os
import re
import json

import httpx
import yt_dlp
import asyncio
import aiofiles
from config import API_URL

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from typing import Dict, List, Optional, Tuple, Union
from youtubesearchpython.__future__ import VideosSearch

from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds
from Opus.utils.downloader import (
    download_audio,
    download_video,
    download_song_audio,
    download_song_video,
)

COOKIE_PATH = "Opus/assets/cookies.txt"
DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = 8 * 1024 * 1024


def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
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


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", (name or "").strip())[:200]


async def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(60, connect=20.0, read=60.0),
        limits=httpx.Limits(max_keepalive_connections=None, max_connections=None, keepalive_expiry=300.0),
        follow_redirects=True,
    )


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
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

    # changed: new helpers for better search ranking
    def _norm(self, s: str) -> List[str]:
        s = (s or "").lower()
        s = re.sub(r"[^\w\s]", " ", s)
        tokens = [t for t in s.split() if t]
        return tokens[:30]

    def _score(self, query: str, title: str, duration: Optional[Union[str, int]]) -> float:
        q = set(self._norm(query))
        t = set(self._norm(title))
        if not t:
            return 0.0
        overlap = len(q & t) / max(1, len(q))
        dur_pen = 0.0
        if isinstance(duration, str):
            try:
                secs = int(time_to_seconds(duration))
            except Exception:
                secs = 0
        elif isinstance(duration, int):
            secs = duration
        else:
            secs = 0
        if secs == 0:
            dur_pen -= 0.05
        if secs <= 45:
            dur_pen -= 0.15
        if "shorts" in (title or "").lower():
            dur_pen -= 0.2
        if "live" in (title or "").lower():
            dur_pen -= 0.25
        return max(0.0, overlap + dur_pen)

    async def _fetch_video_info(self, query: str) -> Optional[Dict]:
        q = query.strip()
        if self._url_pattern.search(q):
            prepared = self._prepare_link(q)
            try:
                stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
                if stdout:
                    info = json.loads(stdout.decode())
                    # normalize to VideosSearch-like keys used elsewhere
                    return {
                        "title": info.get("title", ""),
                        "duration": info.get("duration_string") or info.get("duration"),
                        "thumbnail": (info.get("thumbnail") or "").split("?")[0],
                        "thumbnails": [{"url": (info.get("thumbnail") or "").split("?")[0]}],
                        "id": info.get("id", ""),
                        "webpage_url": info.get("webpage_url") or prepared,
                        "is_live": bool(info.get("is_live")),
                    }
            except Exception:
                pass
        try:
            data = await VideosSearch(q, limit=8).next()
            results = data.get("result", [])
            if not results:
                return None
            best = max(
                results,
                key=lambda r: self._score(q, r.get("title", ""), r.get("duration")),
            )
            return best
        except Exception:
            return None

    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        if isinstance(dt, int):
            ds = dt
            dt_str = None
        else:
            dt_str = dt
            ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dt_str, ds, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        d = info.get("duration") if info else None
        return str(d) if isinstance(d, int) else d

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0] if info else ""

    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        # changed: stricter flags and normalized link to preserve order and skip mixes
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--yes-playlist",
            "--skip-download",
            "--flat-playlist",
            "--get-id",
            "--playlist-end",
            str(limit),
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i and i.lower() != "mix"]

    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info:
                raise ValueError("Track not found via API")
        except Exception:
            prepared = self._prepare_link(link, videoid)
            stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
            if not stdout:
                raise ValueError("Track not found (yt-dlp fallback)")
            info = json.loads(stdout.decode())
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        title = info.get("title", "")
        vid = info.get("id", "")
        duration_val = info.get("duration")
        duration_min = duration_val if isinstance(duration_val, str) else None
        details = {
            "title": title,
            "link": info.get("webpage_url", self._prepare_link(link, videoid)),
            "vidid": vid,
            "duration_min": duration_min,
            "thumb": thumb,
        }
        return details, vid

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
        # changed: rank results beforehand, then index
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results:
            raise IndexError(f"Query type index {query_type} out of range (found 0 results)")
        ranked = sorted(
            results,
            key=lambda r: self._score(link, r.get("title", ""), r.get("duration")),
            reverse=True,
        )
        if query_type >= len(ranked):
            raise IndexError(f"Query type index {query_type} out of range (found {len(ranked)} results)")
        r = ranked[query_type]
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
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)

        if songvideo:
            p = await download_song_video(link, format_id, title)
            return (p, True) if p else (None, None)

        if songaudio:
            p = await download_song_audio(link, format_id, title)
            return (p, True) if p else (None, None)

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                raise ValueError("Unable to fetch live stream link")
            p = await download_video(link, quality=720)
            return (p, True) if p else (None, None)

        p = await download_audio(link)
        return (p, True) if p else (None, None)
