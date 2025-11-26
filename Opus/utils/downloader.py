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
CHUNK_SIZE = 12 * 1024 * 1024
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


def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return COOKIE_PATH
    except Exception:
        pass
    return None


def file_exists(video_id: str, ext: str = None) -> Optional[str]:
    exts = [ext] if ext else ("m4a", "mp3", "webm", "mp4")
    for e in exts:
        path = f"{DOWNLOAD_DIR}/{video_id}.{e}"
        if os.path.exists(path):
            return path
    return None


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", (name or "").strip())[:200]


def _ytdlp_base_opts() -> Dict[str, Union[str, int, bool]]:
    opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 42,
        "http_chunk_size": 1 << 10,
        "socket_timeout": 30,
        "retries": 1,
        "fragment_retries": 1,
        "cachedir": str(CACHE_DIR),
    }
    if cookiefile := _cookiefile_path():
        opts["cookiefile"] = cookiefile
    return opts


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
            headers={"User-Agent": "Mozilla/5.0"},
        )
    return _client


async def _stream_download(url: str, out_path: str, timeout: float) -> bool:
    try:
        client = await _get_client()
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        async with client.stream("GET", url, timeout=timeout) as resp:
            if resp.status_code != 200:
                return False
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


async def api_download_audio(video_id: str, fmt: str = "m4a") -> Optional[str]:
    if not USE_API:
        return None
    client = await _get_client()
    params = {"video_id": video_id, "format": fmt}
    url = f"{SYPHIX_BASE}/stream_id"
    out_path = f"{DOWNLOAD_DIR}/{video_id}.{fmt}"
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        async with client.stream("GET", url, params=params, timeout=120.0) as r:
            if r.status_code != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in r.aiter_bytes(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 0 else None
    except Exception:
        return None


async def api_download_video(video_id_or_link: str, quality: str = "360", wait_timeout: float = 160.0) -> Optional[str]:
    if not USE_API:
        return None
    client = await _get_client()
    if "youtube" in video_id_or_link or "youtu.be" in video_id_or_link:
        yurl = video_id_or_link
    else:
        yurl = f"https://www.youtube.com/watch?v={video_id_or_link}"
    params = {"url": yurl, "format": "mp4", "quality": quality}
    url = f"{SYPHIX_BASE}/stream"
    out_path = f"{DOWNLOAD_DIR}/{extract_video_id(yurl)}.mp4"
    start = time.time()
    backoff = 1.0
    while time.time() - start < wait_timeout:
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            async with client.stream("GET", url, params=params, timeout=120.0) as r:
                if r.status_code == 200:
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in r.aiter_bytes(CHUNK_SIZE):
                            if chunk:
                                await f.write(chunk)
                    return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 0 else None
                if r.status_code >= 500:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, 5.0)
                    continue
                return None
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 5.0)
            continue
    return None


def _download_ytdlp_sync(link: str, opts: dict) -> Optional[str]:
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        preexisting = set()
        for root, _, files in os.walk(DOWNLOAD_DIR):
            for f in files:
                preexisting.add(os.path.join(root, f))
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            vid = info.get("id")
            ext = info.get("ext", "webm")
            expected_by_id = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
            if os.path.exists(expected_by_id) and os.path.getsize(expected_by_id) > 0:
                return expected_by_id
            ydl.download([link])
        post = []
        for root, _, files in os.walk(DOWNLOAD_DIR):
            for f in files:
                path = os.path.join(root, f)
                if path not in preexisting and os.path.getsize(path) > 0:
                    post.append(path)
        if len(post) == 1:
            return post[0]
        for p in post:
            if vid and vid in os.path.basename(p):
                return p
        if os.path.exists(expected_by_id) and os.path.getsize(expected_by_id) > 0:
            return expected_by_id
        return post[0] if post else None
    except Exception:
        return None


async def _run_ytdlp(link: str, opts: dict) -> Optional[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _download_ytdlp_sync, link, opts)


async def download_audio(link: str) -> Optional[str]:
    video_id = extract_video_id(link)
    if cached := file_exists(video_id, "m4a"):
        return cached
    if cached := file_exists(video_id, "mp3"):
        return cached

    async def run():
        api_result = await api_download_audio(video_id, fmt="m4a")
        if api_result and os.path.exists(api_result):
            final_m4a = f"{DOWNLOAD_DIR}/{video_id}.m4a"
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            try:
                os.replace(api_result, final_m4a)
            except Exception:
                pass
            return final_m4a if os.path.exists(final_m4a) else api_result
        opts = _ytdlp_base_opts()
        opts.update({
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": f"{DOWNLOAD_DIR}/{video_id}.%(ext)s",
        })
        return await _run_ytdlp(link, opts)

    return await run()


async def download_video(link: str, quality: int = 360) -> Optional[str]:
    video_id = extract_video_id(link)
    if cached := file_exists(video_id, "mp4"):
        return cached

    async def run():
        api_result = await api_download_video(link, f"{quality}", wait_timeout=160.0)
        if api_result and os.path.exists(api_result):
            return api_result
        height = min(quality, 1080)
        opts = _ytdlp_base_opts()
        opts.update({
            "format": f"best[height<={height}]/best",
            "merge_output_format": "mp4",
        })
        return await _run_ytdlp(link, opts)

    return await run()


async def download_song_video(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe_title = _safe_filename(title)
    video_id = extract_video_id(link)
    out_path = f"{DOWNLOAD_DIR}/{safe_title}.mp4"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    async def run():
        api_vid = await api_download_video(video_id, wait_timeout=160.0)
        if api_vid and os.path.exists(api_vid):
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            final_path = out_path
            with contextlib.suppress(FileNotFoundError):
                os.replace(api_vid, final_path)
            return final_path if os.path.exists(final_path) else None
        opts = _ytdlp_base_opts()
        if format_id:
            opts.update({
                "format": f"{format_id}+140",
                "outtmpl": out_path,
                "merge_output_format": "mp4",
            })
        else:
            opts.update({
                "format": "bestvideo+bestaudio/best",
                "outtmpl": out_path,
                "merge_output_format": "mp4",
            })
        await _run_ytdlp(link, opts)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 0 else None

    return await run()


async def download_song_audio(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe_title = _safe_filename(title)
    video_id = extract_video_id(link)
    out_path = f"{DOWNLOAD_DIR}/{safe_title}.m4a"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    async def run():
        api_audio = await api_download_audio(video_id, fmt="m4a")
        if api_audio and os.path.exists(api_audio):
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            final_path = out_path
            with contextlib.suppress(FileNotFoundError):
                os.replace(api_audio, final_path)
            return final_path if os.path.exists(final_path) else None
        opts = _ytdlp_base_opts()
        if format_id:
            fmt = format_id
        else:
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
        opts.update({
            "format": fmt,
            "outtmpl": f"{DOWNLOAD_DIR}/{safe_title}.%(ext)s",
        })
        await _run_ytdlp(link, opts)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 0 else None

    return await run()
