import asyncio
import contextlib
import os
import re
import time
from typing import Dict, Optional, Union

import aiofiles
import httpx
from yt_dlp import YoutubeDL
from config import API_URL

DOWNLOAD_DIR = "downloads"
CACHE_DIR = "cache"
COOKIE_PATH = "Opus/assets/cookies.txt"
CHUNK_SIZE = 8 * 1024 * 1024
USE_API = True

_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()

SYPHIX_BASE = "https://syphixlabs.opusx.workers.dev"


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    m = re.search(r"youtu\.be/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    m = re.search(r"youtube\.com/shorts/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    m = re.search(r"youtube\.com/embed/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    return link.split("/")[-1].split("?")[0]


def file_exists(video_id: str, ext: str = None) -> Optional[str]:
    exts = [ext] if ext else ("mp3", "m4a", "webm", "mp4")
    for e in exts:
        p = f"{DOWNLOAD_DIR}/{video_id}.{e}"
        if os.path.exists(p):
            return p
    return None


def _ytdlp_base_opts() -> Dict[str, Union[str, int, bool]]:
    return {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 1 << 20,
        "socket_timeout": 30,
        "retries": 1,
        "fragment_retries": 1,
        "cachedir": str(CACHE_DIR),
    }


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client and not _client.is_closed:
        return _client
    async with _client_lock:
        if _client and not _client.is_closed:
            return _client
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0, read=60.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100, keepalive_expiry=300),
            follow_redirects=True,
        )
    return _client


async def _stream(url: str, params: dict, out_path: str, timeout: float) -> bool:
    try:
        client = await _get_client()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        async with client.stream("GET", url, params=params, timeout=timeout) as r:
            if r.status_code != 200:
                return False
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in r.aiter_bytes(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
    except Exception:
        return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


async def download_song_audio(video_id: str) -> Optional[str]:
    out_path = f"{DOWNLOAD_DIR}/{video_id}.mp3"
    ok = await _stream(
        f"{SYPHIX_BASE}/stream_id",
        {"video_id": video_id, "format": "mp3"},
        out_path,
        timeout=120.0
    )
    return out_path if ok else None


async def download_song_video(video_id_or_link: str, quality: str = "360") -> Optional[str]:
    if "youtube" in video_id_or_link:
        url = video_id_or_link
    else:
        url = f"https://www.youtube.com/watch?v={video_id_or_link}"
    out_path = f"{DOWNLOAD_DIR}/{extract_video_id(url)}.mp4"
    ok = await _stream(
        f"{SYPHIX_BASE}/stream",
        {"url": url, "format": "mp4", "quality": quality},
        out_path,
        timeout=160.0
    )
    return out_path if ok else None


def _download_ytdlp_sync(link: str, opts: dict) -> Optional[str]:
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with YoutubeDL(opts) as ydl:
            ydl.download([link])
        video_id = extract_video_id(link)
        path = f"{DOWNLOAD_DIR}/{video_id}.mp3"
        return path if os.path.exists(path) else None
    except Exception:
        return None


async def _run_ytdlp(link: str, opts: dict) -> Optional[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _download_ytdlp_sync, link, opts)


async def download_audio(link: str) -> Optional[str]:
    video_id = extract_video_id(link)

    if cached := file_exists(video_id, "mp3"):
        return cached

    api_result = await api_download_audio(video_id)
    if api_result:
        return api_result

    opts = _ytdlp_base_opts()
    opts.update({
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": f"{DOWNLOAD_DIR}/{video_id}.%(ext)s",
    })
    return await _run_ytdlp(link, opts)


async def download_video(link: str, quality: int = 360) -> Optional[str]:
    video_id = extract_video_id(link)

    if cached := file_exists(video_id, "mp4"):
        return cached

    api_result = await api_download_video(link, str(quality))
    if api_result:
        return api_result

    opts = _ytdlp_base_opts()
    opts.update({
        "format": f"best[height<={quality}]/best",
        "merge_output_format": "mp4",
    })
    return await _run_ytdlp(link, opts)
