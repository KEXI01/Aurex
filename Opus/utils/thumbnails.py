import os
import re
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import FAILED

TEMPLATE_PATH = "Opus/assets/Player.png"

def _resample_lanczos():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS

def safe_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _largest_bright_square(img: Image.Image):
    W, H = img.size
    gray = img.convert("L")
    arr = np.array(gray, dtype=np.uint8)
    left_band = int(W * 0.62)
    sub = arr[:, :left_band]
    thr = int(np.percentile(sub, 92))
    mask = (sub >= thr).astype(np.uint8)
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=np.uint8)

    def neighbors(r, c):
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < h and 0 <= cc < w:
                yield rr, cc

    best = None
    for r in range(h):
        for c in range(w):
            if mask[r, c] and not visited[r, c]:
                stack = [(r, c)]
                visited[r, c] = 1
                min_r = max_r = r
                min_c = max_c = c
                area = 0
                while stack:
                    rr, cc = stack.pop()
                    area += 1
                    if rr < min_r: min_r = rr
                    if rr > max_r: max_r = rr
                    if cc < min_c: min_c = cc
                    if cc > max_c: max_c = cc
                    for nr, nc in neighbors(rr, cc):
                        if mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                bw = max_c - min_c + 1
                bh = max_r - min_r + 1
                if bw and bh:
                    squareness = 1.0 - abs(bw - bh) / float(max(bw, bh))
                else:
                    squareness = 0
                score = area * (0.7 + 0.3 * squareness)
                if best is None or score > best[0]:
                    best = (score, min_c, min_r, max_c, max_r)

    if best:
        _, x0, y0, x1, y1 = best
        size = min(x1 - x0 + 1, y1 - y0 + 1)
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        half = size // 2
        sx0 = max(0, cx - half)
        sy0 = max(0, cy - half)
        sx0 = min(sx0, W - size)
        sy0 = min(sy0, H - size)
        return sx0, sy0, size

    size = int(H * 0.74)
    y0   = int((H - size) * 0.50)
    x0   = int(W * 0.085)
    size = min(size, W - x0 - int(W * 0.5))
    y0 = max(0, min(y0, H - size))
    return x0, y0, size

def _right_text_box(W, H, thumb_box):
    tx0 = thumb_box[0] + thumb_box[2] + int(W * 0.02)
    right_safe_pad = int(W * 0.12)
    tx1 = W - right_safe_pad
    top_margin  = int(H * 0.22)
    bottom_band = int(H * 0.52)
    ty0 = top_margin
    ty1 = bottom_band
    if tx1 <= tx0:
        tx0, tx1 = int(W*0.55), int(W*0.88)
    return tx0, ty0, tx1, ty1

def _fit_and_ellipsize(draw, text, font_path, start_px, min_px, box_w):
    size = start_px
    while size >= min_px:
        f = safe_font(font_path, size)
        w = draw.textbbox((0, 0), text, font=f)[2]
        if w <= box_w:
            return text, f
        size -= 1
    f = safe_font(font_path, min_px)
    lo, hi = 1, len(text)
    best = "…"
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + "…"
        w = draw.textbbox((0, 0), cand, font=f)[2]
        if w <= box_w:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best, f

async def get_thumb(videoid: str):
    final_path = f"cache/{videoid}.png"
    if os.path.isfile(final_path):
        return final_path

    if not os.path.exists(TEMPLATE_PATH):
        return FAILED

    try:
        query = f"https://www.youtube.com/watch?v={videoid}"
        search = VideosSearch(query, limit=1)
        try:
            results = await search.next()
        except TypeError:
            results = search.result()
        if not results or "result" not in results or not results["result"]:
            return FAILED

        r0 = results["result"][0]
        title = re.sub(r"\s+", " ", r0.get("title", "")).strip() or "Unknown Title"

        ch = r0.get("channel")
        if isinstance(ch, dict):
            channel = ch.get("name") or "Youtube"
        elif isinstance(ch, str) and ch.strip():
            channel = ch.strip()
        else:
            channel = "Youtube"

        thumbs = r0.get("thumbnails") or r0.get("thumbnail") or []
        thumb_url = ""
        if isinstance(thumbs, list):
            for t in reversed(thumbs):
                if isinstance(t, dict) and t.get("url"):
                    thumb_url = t["url"].split("?")[0]
                    break
        elif isinstance(thumbs, dict) and thumbs.get("url"):
            thumb_url = thumbs["url"].split("?")[0]
        if not thumb_url:
            return FAILED
    except Exception:
        return FAILED

    os.makedirs("cache", exist_ok=True)
    raw_path = f"cache/raw_{videoid}.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                if resp.status != 200:
                    return FAILED
                async with aiofiles.open(raw_path, "wb") as f:
                    await f.write(await resp.read())
    except Exception:
        return FAILED

    try:
        base = Image.open(TEMPLATE_PATH).convert("RGBA")
        W, H = base.size
        draw = ImageDraw.Draw(base)

        x0, y0, size = _largest_bright_square(base)

        src = Image.open(raw_path).convert("RGBA")
        cover = ImageOps.fit(src, (size, size), method=_resample_lanczos(), centering=(0.5, 0.5))
        base.paste(cover, (x0, y0), cover)

        tx0, ty0, tx1, ty1 = _right_text_box(W, H, (x0, y0, size))
        text_w = max(1, tx1 - tx0)
        text_h = max(1, ty1 - ty0)

        title_font_path = "Opus/assets/font2.ttf"
        channel_font_path = "Opus/assets/font.ttf"

        title_text, title_font = _fit_and_ellipsize(
            draw, title, title_font_path, start_px=44, min_px=24, box_w=text_w
        )
        title_y = ty0
        draw.text((tx0, title_y), title_text, fill=(255, 255, 255), font=title_font)
        tb = draw.textbbox((tx0, title_y), title_text, font=title_font)

        channel_font = safe_font(channel_font_path, 15)
        ch_text = channel
        ch_w = draw.textbbox((0, 0), ch_text, font=channel_font)[2]
        if ch_w > text_w:
            lo, hi = 1, len(ch_text)
            best = "…"
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = ch_text[:mid].rstrip() + "…"
                if draw.textbbox((0, 0), cand, font=channel_font)[2] <= text_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            ch_text = best

        ch_y = tb[3] + int(H * 0.01)
        if ch_y + (draw.textbbox((0,0), ch_text, font=channel_font)[3]) > ty1:
            ch_y = max(ty0, ty1 - (draw.textbbox((0,0), ch_text, font=channel_font)[3] - 0))

        draw.text((tx0, ch_y), ch_text, fill=(255, 255, 255), font=channel_font)

        out = base.convert("RGB")
        out.save(final_path, "PNG")

        try:
            os.remove(raw_path)
        except Exception:
            pass

        return final_path
    except Exception:
        return FAILED
