import asyncio
import contextlib
import os
import re
from typing import Dict, Optional, Union

import aiofiles
import httpx
from yt_dlp import YoutubeDL

DOWNLOAD_DIR = "downloads"
CACHE_DIR = "cache"
COOKIE_PATH = "Opus/assets/cookies.txt"

_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


BROWSER_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


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
    if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
        return COOKIE_PATH
    return None


def file_exists(video_id: str, ext: str = None) -> Optional[str]:
    exts = [ext] if ext else ("mp3", "m4a", "webm", "mp4")
    for e in exts:
        f = f"{DOWNLOAD_DIR}/{video_id}.{e}"
        if os.path.exists(f):
            return f
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
        "cachedir": str(CACHE_DIR),
    }
    cookiefile = _cookiefile_path()
    if cookiefile:
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
            timeout=httpx.Timeout(60, connect=10, read=60),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        )
    return _client


async def _direct_save(url: str, out_path: str) -> bool:
    try:
        client = await _get_client()
        r = await client.get(url)

        print(f"[API CALL] {url} -> {r.status_code}")

        if r.status_code != 200:
            return False

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        async with aiofiles.open(out_path, "wb") as f:
            await f.write(r.content)

        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        print(f"[API ERROR] {url} | {e}")
        return False


async def api_download_audio(video_id: str) -> Optional[str]:
    url = f"https://syphixlabs.opusx.workers.dev/stream_id?video_id={video_id}&format=m4a"
    out_path = f"{DOWNLOAD_DIR}/{video_id}.mp3"
    ok = await _direct_save(url, out_path)
    print(f"[API AUDIO] {video_id} -> {ok}")
    return out_path if ok else None


async def api_download_video(video_id: str) -> Optional[str]:
    url = f"https://syphixlabs.opusx.workers.dev/stream_id?video_id={video_id}&format=mp4"
    out_path = f"{DOWNLOAD_DIR}/{video_id}.mp4"
    ok = await _direct_save(url, out_path)
    print(f"[API VIDEO] {video_id} -> {ok}")
    return out_path if ok else None


def _download_ytdlp_sync(link: str, opts: dict) -> Optional[str]:
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        before = set(os.listdir(DOWNLOAD_DIR))
        with YoutubeDL(opts) as ydl:
            ydl.download([link])
        after = set(os.listdir(DOWNLOAD_DIR)) - before
        if not after:
            return None
        out = os.path.join(DOWNLOAD_DIR, list(after)[0])
        return out if os.path.getsize(out) > 0 else None
    except:
        return None


async def _run_ytdlp(link: str, opts: dict) -> Optional[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _download_ytdlp_sync, link, opts)


async def download_audio(link: str) -> Optional[str]:
    video_id = extract_video_id(link)

    if cached := file_exists(video_id, "mp3"):
        return cached

    api_file = await api_download_audio(video_id)
    if api_file:
        return api_file

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

    api_file = await api_download_video(video_id)
    if api_file:
        return api_file

    opts = _ytdlp_base_opts()
    opts.update({
        "format": f"best[height<={quality}]/best",
        "merge_output_format": "mp4",
    })
    return await _run_ytdlp(link, opts)


async def download_song_video(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe = _safe_filename(title)
    video_id = extract_video_id(link)
    out_path = f"{DOWNLOAD_DIR}/{safe}.mp4"

    if os.path.exists(out_path):
        return out_path

    api_file = await api_download_video(video_id)
    if api_file:
        os.replace(api_file, out_path)
        return out_path

    opts = _ytdlp_base_opts()
    if format_id:
        opts.update({"format": f"{format_id}+140", "outtmpl": out_path, "merge_output_format": "mp4"})
    else:
        opts.update({"format": "bestvideo+bestaudio/best", "outtmpl": out_path, "merge_output_format": "mp4"})
    await _run_ytdlp(link, opts)
    return out_path if os.path.exists(out_path) else None


async def download_song_audio(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe = _safe_filename(title)
    video_id = extract_video_id(link)
    out_path = f"{DOWNLOAD_DIR}/{safe}.mp3"

    if os.path.exists(out_path):
        return out_path

    api_file = await api_download_audio(video_id)
    if api_file:
        os.replace(api_file, out_path)
        return out_path

    opts = _ytdlp_base_opts()
    fmt = format_id if format_id else "bestaudio/best"
    opts.update({
        "format": fmt,
        "outtmpl": f"{DOWNLOAD_DIR}/{safe}.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    })
    await _run_ytdlp(link, opts)
    return out_path if os.path.exists(out_path) else None
