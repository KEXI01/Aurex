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
CHUNK_SIZE = 4 * 1024 * 1024
USE_API = True

_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


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


def _looks_like_video_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]{6,}", value))


def _audio_exists(video_id: str) -> Optional[str]:
    for e in ("m4a", "opus", "mp3", "webm"):
        path = f"{DOWNLOAD_DIR}/{video_id}.{e}"
        if os.path.exists(path):
            return path
    return None


def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return COOKIE_PATH
    except Exception:
        pass
    return None


def file_exists(video_id: str, ext: str = None) -> Optional[str]:
    exts = [ext] if ext else ("mp3", "m4a", "webm", "mp4")
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
        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 1 << 20,
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
            timeout=httpx.Timeout(60.0, connect=20.0, read=60.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100, keepalive_expiry=300),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    return _client


async def _api_fetch_json(path: str, params: dict | None = None, timeout: float = 30.0) -> Optional[dict]:
    if not USE_API or not API_URL:
        return None
    try:
        client = await _get_client()
        backoff = 0.2
        for _ in range(1):
            r = await client.get(f"{API_URL.rstrip('/')}{path}", params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code >= 500:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            return None
    except Exception:
        return None
    return None


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


async def api_download_audio(video_id: str) -> Optional[str]:
    if not USE_API or not API_URL:
        return None
    try:
        client = await _get_client()
        base = API_URL.rstrip("/")
        yurl = f"https://youtu.be/{video_id}"

        r = await client.get(
            base,
            params={"url": yurl},
            timeout=60.0,
        )
        if r.status_code != 200:
            return None

        data = r.json()
        if data.get("status") != 200 or data.get("successful") != "success":
            return None

        payload = data.get("data") or {}
        download_info = payload.get("download") or {}

        dl_url = download_info.get("url")
        filename = download_info.get("filename") or f"{video_id}.mp3"
        if not dl_url:
            return None

        _, ext = os.path.splitext(filename)
        ext = (ext or ".mp3").lstrip(".") or "mp3"

        out_path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        ok = await _stream_download(dl_url, out_path, timeout=120.0)
        if ok and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        return None
    return None


async def api_download_video(video_id: str, wait_timeout: float = 160.0) -> Optional[str]:
    if not USE_API or not API_URL:
        return None
    try:
        client = await _get_client()
        base = API_URL.rstrip("/")
        yurl = f"https://youtu.be/{video_id}"

        r = await client.get(
            base,
            params={"url": yurl, "format": "mp4"},
            timeout=wait_timeout,
        )
        if r.status_code != 200:
            return None

        data = r.json()
        if data.get("status") != 200 or data.get("successful") != "success":
            return None

        payload = data.get("data") or {}
        download_info = payload.get("download") or {}

        dl_url = download_info.get("url")
        filename = download_info.get("filename") or f"{video_id}.mp4"
        if not dl_url:
            return None

        _, ext = os.path.splitext(filename)
        ext = (ext or ".mp4").lstrip(".") or "mp4"

        out_path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        dl_timeout = max(wait_timeout, 60.0)

        ok = await _stream_download(dl_url, out_path, timeout=dl_timeout)
        if ok and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        return None
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
    raw = link.strip()
    if _looks_like_video_id(raw):
        video_id = raw
    else:
        video_id = extract_video_id(raw)
    if cached := _audio_exists(video_id):
        return cached

    async def run():
        api_result = await api_download_audio(video_id)
        if api_result and os.path.exists(api_result):
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

    return await run()


async def download_video(link: str, quality: int = 360) -> Optional[str]:
    video_id = extract_video_id(link)
    if cached := file_exists(video_id, "mp4"):
        return cached

    async def run():
        api_result = await api_download_video(video_id, wait_timeout=160.0)
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
    raw = link.strip()
    if _looks_like_video_id(raw):
        video_id = raw
    else:
        video_id = extract_video_id(raw)
    out_path = f"{DOWNLOAD_DIR}/{safe_title}.mp3"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    async def run():
        api_audio = await api_download_audio(video_id)
        if api_audio and os.path.exists(api_audio):
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            ext = os.path.splitext(api_audio)[1] or ".mp3"
            final_path = f"{DOWNLOAD_DIR}/{safe_title}{ext}"
            with contextlib.suppress(FileNotFoundError):
                os.replace(api_audio, final_path)
            return final_path if os.path.exists(final_path) else None
        opts = _ytdlp_base_opts()
        if format_id:
            fmt = format_id
        else:
            fmt = "bestaudio/best"
        opts.update({
            "format": fmt,
            "outtmpl": f"{DOWNLOAD_DIR}/{safe_title}.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        await _run_ytdlp(link, opts)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 0 else None

    return await run()
