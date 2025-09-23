import asyncio
import aiohttp
import aiofiles
import os
import re
from typing import Optional, Dict, Union, List
from yt_dlp import YoutubeDL
#from config import API_URL

API_URL = "https://ar-api-iauy.onrender.com/mp3youtube"

cookies_file = "Cookies/cookies.txt"
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)


def extract_video_id(link: str) -> str:
    """Extract YouTube video ID from link."""
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return link.split("/")[-1].split("?")[0]


def safe_filename(name: str) -> str:
    """Make safe filename (avoid invalid characters)."""
    return re.sub(r"[\\/*?\"<>|]", "_", name).strip()[:100]


def file_exists(video_id: str, file_type: str = "audio") -> Optional[str]:
    """Check if file already exists for video ID."""
    extensions = ["mp3"] if file_type == "audio" else ["mp4", "mkv", "webm"]

    for ext in extensions:
        path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(path):
            return path

        for file in os.listdir(download_folder):
            if file.startswith(video_id) and file.endswith(f".{ext}"):
                return f"{download_folder}/{file}"

    return None


async def api_download(link: str, file_type: str = "audio") -> Optional[str]:
    """Try downloading using external API with larger chunks (1MB)."""
    video_id = extract_video_id(link)
    try:
        timeout = aiohttp.ClientTimeout(total=20, connect=10)
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300, ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            if file_type == "audio":
                api_url = f"{API_URL}?url=https://youtube.com/watch?v={video_id}&format=mp3&audioBitrate=128"
                expected_ext = "mp3"
            else:
                api_url = f"{API_URL}?url=https://youtube.com/watch?v={video_id}&format=mp4"
                expected_ext = "mp4"

            async with session.get(api_url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                if data.get("status") != 200 or data.get("successful") != "success":
                    return None

                download_url = data["data"]["download"]["url"]
                filename = f"{video_id}.{expected_ext}"
                path = f"{download_folder}/{filename}"

                async with session.get(download_url) as file_response:
                    if file_response.status != 200:
                        return None
                    async with aiofiles.open(path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                            await f.write(chunk)

                if not os.path.exists(path) or os.path.getsize(path) < 1024:
                    if os.path.exists(path):
                        os.remove(path)
                    return None

                return path
    except Exception:
        return None


def _download_ytdlp(link: str, opts: Dict) -> Union[None, str, List[str]]:
    """Helper to run yt-dlp sync inside executor."""
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)

            # Playlist
            if "entries" in info:
                results = []
                ydl.download([link])  # Download playlist

                for entry in info["entries"]:
                    vid = entry.get("id")
                    if not vid:
                        continue
                    for file in os.listdir(download_folder):
                        if file.startswith(vid):
                            results.append(f"{download_folder}/{file}")
                return results

            # Single video
            vid = info.get("id")
            ext = "mp3" if "postprocessors" in opts else "mp4"
            expected_filename = f"{download_folder}/{vid}.{ext}"

            ydl.download([link])

            if os.path.exists(expected_filename):
                return expected_filename

            for file in os.listdir(download_folder):
                if file.startswith(vid):
                    return f"{download_folder}/{file}"

            return None

    except Exception:
        return None


async def yt_dlp_download(link: str, type: str, format_id: str = None) -> Union[None, str, List[str]]:
    """Run yt-dlp in async wrapper for audio/video download."""
    loop = asyncio.get_running_loop()

    def is_restricted() -> bool:
        return os.path.exists(cookies_file)

    common_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "geo_bypass": True,
        "geo_bypass_country": "IN",
        "concurrent_fragment_downloads": 16,   # boost parallelism
        "http_chunk_size": 1024 * 1024,        # 1MB chunks
    }

    if type in ["audio", "song_audio"]:
        opts = {
            **common_opts,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "cookiefile": cookies_file if is_restricted() else None,
            "outtmpl": f"{download_folder}/%(id)s.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        format_str = "best[height<=720]/bestvideo[height<=720]+bestaudio/best[height<=720]"
        if format_id:
            format_str = format_id
        opts = {
            **common_opts,
            "format": format_str,
            "cookiefile": cookies_file if is_restricted() else None,
            "outtmpl": f"{download_folder}/%(id)s.%(ext)s",
            "merge_output_format": "mp4",
            "prefer_ffmpeg": True,
        }

    return await loop.run_in_executor(None, _download_ytdlp, link, opts)


async def download_audio_concurrent(link: str) -> Union[None, str, List[str]]:
    """Try API first, fallback to yt-dlp for audio. Handles playlists too."""
    existing = file_exists(extract_video_id(link), "audio")
    if existing:
        return existing

    try:
        api_result = await asyncio.wait_for(api_download(link, file_type="audio"), timeout=45)
        if api_result:
            return api_result
    except Exception:
        pass

    try:
        yt_result = await asyncio.wait_for(yt_dlp_download(link, type="audio"), timeout=180)
        return yt_result
    except Exception:
        pass

    return None


async def download_video_concurrent(link: str) -> Union[None, str, List[str]]:
    """Try API first, fallback to yt-dlp for video. Handles playlists too."""
    existing = file_exists(extract_video_id(link), "video")
    if existing:
        return existing

    try:
        api_result = await asyncio.wait_for(api_download(link, file_type="video"), timeout=45)
        if api_result:
            return api_result
    except Exception:
        pass

    try:
        yt_result = await asyncio.wait_for(yt_dlp_download(link, type="video"), timeout=240)
        return yt_result
    except Exception:
        pass

    return None
