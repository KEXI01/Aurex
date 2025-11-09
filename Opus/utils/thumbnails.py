import os
import re
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from youtubesearchpython.__future__ import VideosSearch
from config import FAILED

TEMPLATE_PATH = "Opus/assets/Player.png"

def _resample():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS

def safe_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _detect_left_square(img):
    W, H = img.size
    gray = img.convert("L")
    arr = np.array(gray, dtype=np.uint8)
    x_end = int(W * 0.6)
    sub = arr[:, :x_end]
    thr = max(180, int(np.percentile(sub, 90)))
    mask = (sub >= thr).astype(np.uint8)
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=np.uint8)
    def nbrs(r, c):
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
                    for nr, nc in nbrs(rr, cc):
                        if mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                bw = max_c - min_c + 1
                bh = max_r - min_r + 1
                if bw == 0 or bh == 0:
                    continue
                sq = 1 - abs(bw - bh) / float(max(bw, bh))
                score = area * (0.6 + 0.4 * sq)
                if best is None or score > best[0]:
                    best = (score, min_c, min_r, max_c, max_r)
    if best:
        _, x0, y0, x1, y1 = best
        s = min(x1 - x0 + 1, y1 - y0 + 1)
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        half = s // 2
        sx0 = max(0, min(cx - half, W - s))
        sy0 = max(0, min(cy - half, H - s))
        inset = max(4, int(min(W, H) * 0.004))
        return sx0 + inset, sy0 + inset, s - inset * 2
    s = int(H * 0.74)
    y0 = int((H - s) * 0.50)
    x0 = int(W * 0.085)
    s = min(s, W - x0 - int(W * 0.5))
    y0 = max(0, min(y0, H - s))
    inset = max(4, int(min(W, H) * 0.004))
    return x0 + inset, y0 + inset, s - inset * 2

def _text_safe_box(W, H, thumb):
    x0, y0, s = thumb
    gap = max(18, int(W * 0.013))
    tx0 = x0 + s + gap
    right_pad = int(W * 0.12)
    tx1 = W - right_pad
    ty0 = y0 + int(s * 0.18)
    ty1 = y0 + int(s * 0.42)
    if tx1 <= tx0:
        tx0, tx1 = int(W * 0.56), int(W * 0.88)
    ty0 = max(ty0, int(H * 0.18))
    ty1 = min(ty1, int(H * 0.56))
    return tx0, ty0, tx1, ty1

def _ellipsize(draw, text, font, max_w):
    if not text:
        return ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    lo, hi = 1, len(text)
    best = "…"
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + "…"
        if draw.textbbox((0, 0), cand, font=font)[2] <= max_w:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best

def _fit_font(draw, text, path, start_px, min_px, max_w):
    s = start_px
    while s >= min_px:
        f = safe_font(path, s)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        s -= 1
    return safe_font(path, min_px)

async def get_thumb(videoid):
    out_path = f"cache/{videoid}.png"
    if os.path.isfile(out_path):
        return out_path
    if not os.path.exists(TEMPLATE_PATH):
        return FAILED
    try:
        q = f"https://www.youtube.com/watch?v={videoid}"
        vs = VideosSearch(q, limit=1)
        try:
            res = await vs.next()
        except TypeError:
            res = vs.result()
        if not res or "result" not in res or not res["result"]:
            return FAILED
        r0 = res["result"][0]
        title = re.sub(r"\s+", " ", r0.get("title", "")).strip() or "Unknown Title"
        ch = r0.get("channel")
        if isinstance(ch, dict):
            channel = (ch.get("name") or "Youtube").strip() or "Youtube"
        elif isinstance(ch, str) and ch.strip():
            channel = ch.strip()
        else:
            channel = "Youtube"
        thumbs = r0.get("thumbnails") or r0.get("thumbnail") or []
        url = ""
        if isinstance(thumbs, list):
            for t in reversed(thumbs):
                if isinstance(t, dict) and t.get("url"):
                    url = t["url"].split("?")[0]
                    break
        elif isinstance(thumbs, dict) and thumbs.get("url"):
            url = thumbs["url"].split("?")[0]
        if not url:
            return FAILED
    except Exception:
        return FAILED
    os.makedirs("cache", exist_ok=True)
    raw_path = f"cache/raw_{videoid}.jpg"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return FAILED
                async with aiofiles.open(raw_path, "wb") as f:
                    await f.write(await r.read())
    except Exception:
        return FAILED
    try:
        base = Image.open(TEMPLATE_PATH).convert("RGBA")
        W, H = base.size
        draw = ImageDraw.Draw(base)
        x0, y0, s = _detect_left_square(base)
        src = Image.open(raw_path).convert("RGBA")
        cover = ImageOps.fit(src, (s, s), method=_resample(), centering=(0.5, 0.5))
        mask = Image.new("L", (s, s), 0)
        rad = max(12, int(s * 0.06))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, s, s), radius=rad, fill=255)
        base.paste(cover, (x0, y0), mask)
        tx0, ty0, tx1, ty1 = _text_safe_box(W, H, (x0, y0, s))
        text_w = max(1, tx1 - tx0)
        title_font_path = "Opus/assets/font.ttf"
        channel_font_path = "Opus/assets/font2.ttf"
        title_font = _fit_font(draw, title, title_font_path, start_px=52, min_px=28, max_w=text_w)
        title_text = _ellipsize(draw, title, title_font, text_w)
        draw.text((tx0, ty0), title_text, fill=(255, 255, 255), font=title_font)
        tb = draw.textbbox((tx0, ty0), title_text, font=title_font)
        ch_y = tb[3] + max(6, int(H * 0.007))
        ch_font = safe_font(channel_font_path, 28)
        ch_text = _ellipsize(draw, channel, ch_font, text_w)
        if ch_y > ty1 - (draw.textbbox((0, 0), ch_text, font=ch_font)[3] - draw.textbbox((0, 0), ch_text, font=ch_font)[1]):
            ch_y = max(ty0, ty1 - (draw.textbbox((0, 0), ch_text, font=ch_font)[3] - draw.textbbox((0, 0), ch_text, font=ch_font)[1]))
        draw.text((tx0, ch_y), ch_text, fill=(255, 255, 255), font=ch_font)
        out = base.convert("RGB")
        out.save(out_path, "PNG")
        try:
            os.remove(raw_path)
        except Exception:
            pass
        return out_path
    except Exception:
        return FAILED
