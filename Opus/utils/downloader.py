import asyncio
import os
import re
from typing import Optional, Dict, Union, List

import aiofiles
import httpx
from yt_dlp import YoutubeDL
from config import API_URL

cookies_file = "Opus/assets/cookies.txt"
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)

API_DOWNLOAD_MAX_RETRIES = 1
CHUNK_SIZE = 4 * 1024 * 1024
API_TIMEOUT_SECONDS = 120


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


def safe_filename(name: str) -> str:
    return re.sub(r"[\\/*?\"<>|]", "_", (name or "").strip())[:150]


def file_exists(video_id: str, file_type: str = "audio") -> Optional[str]:
    if file_type == "audio":
        exts = ["mp3", "m4a", "opus", "webm", "mp4", "mkv"]
    else:
        exts = ["mp4", "mkv", "webm"]
    for ext in exts:
        path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    for file in os.listdir(download_folder):
        for ext in exts:
            if file.endswith(f".{ext}") and file.startswith(video_id):
                full = f"{download_folder}/{file}"
                if os.path.getsize(full) > 0:
                    return full
    return None


def _ext_from_filename(fn: str, default: str) -> str:
    fn = (fn or "").strip()
    if "." in fn:
        ext = fn.rsplit(".", 1)[-1].strip().lower()
        if re.fullmatch(r"[0-9a-z]{1,6}", ext):
            return ext
    return default


async def api_download(link: str, file_type: str = "audio", audio_format: str = "m4a") -> Optional[str]:
    if "youtube.com" not in link and "youtu.be" not in link:
        video_id = extract_video_id(link)
        link = f"https://www.youtube.com/watch?v={video_id}"
    else:
        video_id = extract_video_id(link)

    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    file_headers = {
        "User-Agent": base_headers["User-Agent"],
        "Accept": "*/*",
    }
    timeout = httpx.Timeout(API_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=base_headers,
        ) as client:
            if file_type == "audio":
                fmt = (audio_format or "m4a").lower()
                api_url = f"{API_URL}?url={link}&format={fmt}"
                resp = await client.get(api_url)
                if resp.status_code != 200:
                    return None
                ct = resp.headers.get("content-type", "")
                if "application/json" not in ct:
                    return None
                data = resp.json() if resp.content else {}
                if data.get("status") != "tunnel":
                    return None
                download_url = data.get("url")
                if not download_url:
                    return None
                filename = data.get("filename") or ""
                ext = _ext_from_filename(filename, fmt)
                path = f"{download_folder}/{video_id}.{ext}"

                for _ in range(API_DOWNLOAD_MAX_RETRIES):
                    if os.path.exists(path):
                        os.remove(path)
                    try:
                        async with client.stream("GET", download_url, headers=file_headers) as r:
                            if r.status_code != 200:
                                continue
                            async with aiofiles.open(path, "wb") as f:
                                async for chunk in r.aiter_bytes(CHUNK_SIZE):
                                    if not chunk:
                                        break
                                    await f.write(chunk)
                    except Exception:
                        continue

                    if not os.path.exists(path):
                        continue
                    if os.path.getsize(path) < 1024 * 100:
                        os.remove(path)
                        continue
                    return path

                return None

            api_url = f"{API_URL}?url={link}&format=mp4"
            resp = await client.get(api_url)
            if resp.status_code != 200:
                return None
            ct = resp.headers.get("content-type", "")
            if "application/json" not in ct:
                return None
            data = resp.json() if resp.content else {}
            if data.get("status") != "tunnel":
                return None
            download_url = data.get("url")
            if not download_url:
                return None
            filename = data.get("filename") or ""
            ext = _ext_from_filename(filename, "mp4")
            path = f"{download_folder}/{video_id}.{ext}"

            for _ in range(API_DOWNLOAD_MAX_RETRIES):
                if os.path.exists(path):
                    os.remove(path)
                try:
                    async with client.stream("GET", download_url, headers=file_headers) as r:
                        if r.status_code != 200:
                            continue
                        async with aiofiles.open(path, "wb") as f:
                            async for chunk in r.aiter_bytes(CHUNK_SIZE):
                                if not chunk:
                                    break
                                await f.write(chunk)
                except Exception:
                    continue

                if not os.path.exists(path):
                    continue
                if os.path.getsize(path) < 1024 * 100:
                    os.remove(path)
                    continue
                return path

            return None

    except Exception:
        return None


def _download_ytdlp(link: str, opts: Dict) -> Union[None, str, List[str]]:
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            if "entries" in info:
                results: List[str] = []
                ydl.download([link])
                for entry in info["entries"]:
                    vid = entry.get("id")
                    if not vid:
                        continue
                    for file in os.listdir(download_folder):
                        if file.startswith(vid):
                            full = f"{download_folder}/{file}"
                            if os.path.getsize(full) > 0:
                                results.append(full)
                return results
            vid = info.get("id")
            ext = "mp3" if "postprocessors" in opts else "mp4"
            expected = f"{download_folder}/{vid}.{ext}"
            ydl.download([link])
            if os.path.exists(expected) and os.path.getsize(expected) > 0:
                return expected
            for file in os.listdir(download_folder):
                if file.startswith(vid):
                    full = f"{download_folder}/{file}"
                    if os.path.getsize(full) > 0:
                        return full
            return None
    except Exception:
        return None


async def yt_dlp_download(link: str, type: str, format_id: str = None, outtmpl: Optional[str] = None) -> Union[None, str, List[str]]:
    loop = asyncio.get_running_loop()

    def is_restricted() -> bool:
        return os.path.exists(cookies_file)

    common_opts: Dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "geo_bypass": True,
        "concurrent_fragment_downloads": 32,
        "outtmpl": outtmpl or f"{download_folder}/%(id)s.%(ext)s",
    }

    if type in ["audio", "song_audio"]:
        opts = {
            **common_opts,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        if is_restricted():
            opts["cookiefile"] = cookies_file
    else:
        fmt = format_id or "best[height<=720]/bestvideo[height<=720]+bestaudio/best[height<=720]"
        opts = {
            **common_opts,
            "format": fmt,
            "merge_output_format": "mp4",
            "prefer_ffmpeg": True,
        }
        if is_restricted():
            opts["cookiefile"] = cookies_file

    return await loop.run_in_executor(None, _download_ytdlp, link, opts)


async def download_audio(link: str) -> Optional[str]:
    vid = extract_video_id(link)
    existing = file_exists(vid, "audio")
    if existing:
        return existing
    try:
        api_result = await asyncio.wait_for(
            api_download(link, file_type="audio", audio_format="m4a"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if api_result and os.path.exists(api_result) and os.path.getsize(api_result) > 0:
            return api_result
    except Exception:
        pass
    try:
        yt_result = await asyncio.wait_for(
            yt_dlp_download(link, type="audio"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if isinstance(yt_result, list):
            return yt_result[0] if yt_result else None
        return yt_result
    except Exception:
        return None


async def download_video(link: str, quality: int = 360) -> Optional[str]:
    vid = extract_video_id(link)
    existing = file_exists(vid, "video")
    if existing:
        return existing
    try:
        api_result = await asyncio.wait_for(
            api_download(link, file_type="video"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if api_result and os.path.exists(api_result) and os.path.getsize(api_result) > 0:
            return api_result
    except Exception:
        pass
    try:
        yt_result = await asyncio.wait_for(
            yt_dlp_download(link, type="video"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if isinstance(yt_result, list):
            return yt_result[0] if yt_result else None
        return yt_result
    except Exception:
        return None


async def download_song_audio(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe_title = safe_filename(title or "audio")
    out_path_base = f"{download_folder}/{safe_title}.mp3"
    if os.path.exists(out_path_base) and os.path.getsize(out_path_base) > 0:
        return out_path_base

    try:
        api_result = await asyncio.wait_for(
            api_download(link, file_type="audio", audio_format="m4a"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if api_result and os.path.exists(api_result) and os.path.getsize(api_result) > 0:
            ext = os.path.splitext(api_result)[1] or ".mp3"
            final_path = f"{download_folder}/{safe_title}{ext}"
            if api_result != final_path:
                try:
                    os.replace(api_result, final_path)
                except Exception:
                    final_path = api_result
            return final_path
    except Exception:
        pass

    try:
        outtmpl = f"{download_folder}/{safe_title}.%(ext)s"
        yt_result = await asyncio.wait_for(
            yt_dlp_download(link, type="song_audio", format_id=format_id or None, outtmpl=outtmpl),
            timeout=API_TIMEOUT_SECONDS,
        )
        if isinstance(yt_result, list):
            return yt_result[0] if yt_result else None
        return yt_result
    except Exception:
        return None


async def download_song_video(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    safe_title = safe_filename(title or "video")
    out_path_base = f"{download_folder}/{safe_title}.mp4"
    if os.path.exists(out_path_base) and os.path.getsize(out_path_base) > 0:
        return out_path_base

    try:
        api_result = await asyncio.wait_for(
            api_download(link, file_type="video"),
            timeout=API_TIMEOUT_SECONDS,
        )
        if api_result and os.path.exists(api_result) and os.path.getsize(api_result) > 0:
            ext = os.path.splitext(api_result)[1] or ".mp4"
            final_path = f"{download_folder}/{safe_title}{ext}"
            if api_result != final_path:
                try:
                    os.replace(api_result, final_path)
                except Exception:
                    final_path = api_result
            return final_path
    except Exception:
        pass

    try:
        outtmpl = f"{download_folder}/{safe_title}.%(ext)s"
        yt_result = await asyncio.wait_for(
            yt_dlp_download(link, type="video", format_id=format_id or None, outtmpl=outtmpl),
            timeout=API_TIMEOUT_SECONDS,
        )
        if isinstance(yt_result, list):
            return yt_result[0] if yt_result else None
        return yt_result
    except Exception:
        return None
