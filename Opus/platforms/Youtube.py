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


# -------------------- small helpers (non-breaking) --------------------

def _is_yt_url(text: str) -> bool:
    return bool(re.search(r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/", text or "", re.I))


async def _videos_search_robust(query: str, limit: int = 10) -> List[Dict]:
    """
    Use youtubesearchpython only (no yt-dlp search).
    Multiple passes to handle short/ambiguous queries like 'pal pal', 'bargad'.
    Returns the raw 'result' items.
    """
    q = (query or "").strip()
    if not q:
        return []

    async def run_once(qtext: str, lim: int) -> List[Dict]:
        try:
            data = await VideosSearch(qtext, limit=lim).next()
            return data.get("result", []) or []
        except Exception:
            return []

    # 1) raw
    res = await run_once(q, limit)
    if res:
        return res

    # 2) exact phrase for multi-word queries
    if " " in q:
        res = await run_once(f"\"{q}\"", limit)
        if res:
            return res

    # 3) light bias words (non-breaking)
    for suffix in (" song", " video", " official", " lyrics"):
        res = await run_once(q + suffix, limit)
        if res:
            return res

    # 4) sanitize punctuation / collapse spaces
    q2 = re.sub(r"[^\w\s]", " ", q, flags=re.U).strip()
    q2 = re.sub(r"\s+", " ", q2)
    if q2 and q2 != q:
        res = await run_once(q2, limit)
        if res:
            return res

    # 5) lower/title as a last cheap try
    res = await run_once(q.lower(), limit)
    if res:
        return res
    return await run_once(q.title(), limit)


# ----------------------

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
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link or "youtube.com/embed/" in link:
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

    async def _fetch_video_info(self, query: str) -> Optional[Dict]:
        q = self._prepare_link(query)

        if _is_yt_url(q):
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, **({"cookiefile": _cookiefile_path()} if _cookiefile_path() else {})}) as ydl:
                try:
                    info = ydl.extract_info(q, download=False)
                    if info.get("entries"):
                        info = info["entries"][0]
                    return info
                except Exception:
                    return None

        results = await _videos_search_robust(q, limit=1)
        return results[0] if results else None

    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live")) if isinstance(info, dict) else False
        except json.JSONDecodeError:
            return False

    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if isinstance(dt, str) and dt else (int(dt) if isinstance(dt, (int, float)) else 0)
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), (dt if isinstance(dt, str) else None), ds, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        d = info.get("duration") if info else None
        if isinstance(d, (int, float)):
            s = int(d)
            h, rem = divmod(s, 3600)
            m, s = divmod(rem, 60)
            return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"
        return d

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
        """
        Queries -> VideosSearch (robust, no yt-dlp search)
        Direct URLs -> yt-dlp metadata (not a search)
        """
        prepared = self._prepare_link(link, videoid)
        info: Optional[Dict] = None

        if _is_yt_url(prepared):
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, **({"cookiefile": _cookiefile_path()} if _cookiefile_path() else {})}) as ydl:
                try:
                    info = ydl.extract_info(prepared, download=False)
                    if info.get("entries"):
                        info = info["entries"][0]
                except Exception:
                    info = None
        else:
            results = await _videos_search_robust(prepared, limit=5)
            if results:
                info = results[0]

        if not info:
            raise ValueError("Track not found")

        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        vidid = info.get("id", "")
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", f"https://www.youtube.com/watch?v={vidid}" if vidid else prepared),
            "vidid": vidid,
            "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
            "thumb": thumb,
        }
        return details, vidid

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
        results = await _videos_search_robust(self._prepare_link(link, videoid), limit=10)
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results) if results else 0} results)")
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
