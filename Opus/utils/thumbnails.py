import os
import re
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
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

def _find_bright_rows_cols(arr, axis=0, frac=0.55, smooth=7):
    import numpy as _np
    h, w = arr.shape
    thr = max(170, int(_np.percentile(arr, 85)))
    mask = (arr >= thr).astype(_np.uint8)
    proj = mask.mean(axis=1) if axis == 0 else mask.mean(axis=0)
    k = max(3, int(smooth))
    win = _np.ones(k, dtype=float) / k
    proj = _np.convolve(proj, win, mode="same")
    cut = proj.max() * frac
    idx = _np.where(proj >= cut)[0]
    bands = []
    if idx.size:
        start = idx[0]
        prev = idx[0]
        for v in idx[1:]:
            if v == prev + 1:
                prev = v
            else:
                bands.append((start, prev))
                start, prev = v, v
        bands.append((start, prev))
    centers = _np.array([(a + b) // 2 for (a, b) in bands], dtype=int)
    return centers

def _rounded_mask(side, radius):
    m = Image.new("L", (side, side), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill=255)
    return m

def _detect_left_square(img):
    W, H = img.size
    gray = img.convert("L")
    arr = np.array(gray, dtype=np.uint8)
    x_end = int(W * 0.62)
    margin = max(8, int(min(W, H) * 0.01))
    sub = arr[margin:H - margin, margin:x_end]
    thr = max(200, int(np.percentile(sub, 92)))
    mask = (sub >= thr).astype(np.uint8)
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=np.uint8)
    best = None
    def nbrs(r, c):
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < h and 0 <= cc < w:
                yield rr, cc
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
                    min_r = min(min_r, rr); max_r = max(max_r, rr)
                    min_c = min(min_c, cc); max_c = max(max_c, cc)
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
    if not best:
        s = int(H * 0.72)
        y0 = int((H - s) * 0.50)
        x0 = int(W * 0.085)
        s = min(s, W - x0 - int(W * 0.5))
        x0 = max(margin, x0)
        y0 = max(margin, min(y0, H - s - margin))
        radius = max(14, int(s * 0.07))
        return x0, y0, s, _rounded_mask(s, radius)
    _, x0, y0, x1, y1 = best
    x0 += margin; y0 += margin
    x1 += margin; y1 += margin
    s = min(x1 - x0 + 1, y1 - y0 + 1)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    half = s // 2
    sx0 = max(0, min(cx - half, W - s))
    sy0 = max(0, min(cy - half, H - s))
    inset = max(10, int(min(W, H) * 0.012))
    inner_s = s - inset * 2
    radius = max(14, int(inner_s * 0.07))
    return sx0 + inset, sy0 + inset, inner_s, _rounded_mask(inner_s, radius)

def _measure_ui_guides(img, thumb_box):
    W, H = img.size
    gray = np.array(img.convert("L"), dtype=np.uint8)
    rx0 = int(W * 0.45)
    right = gray[:, rx0:]
    bar_rows = _find_bright_rows_cols(right, axis=0, frac=0.65, smooth=9)
    bar_rows = np.clip(bar_rows + 0, 0, right.shape[0]-1)
    bars = []
    for r in bar_rows:
        if not bars or abs(r - bars[-1]) > int(H * 0.06):
            bars.append(r)
    if len(bars) > 2:
        bars = [bars[0], bars[-1]]
    bars = [int(r) for r in bars]
    col_centers = _find_bright_rows_cols(right, axis=1, frac=0.55, smooth=9)
    if col_centers.size:
        icon_col = int(col_centers.max())
        tx1 = rx0 + icon_col - max(18, int(W * 0.015))
    else:
        tx1 = int(W * 0.88)
    x0, y0, s = thumb_box
    gap = max(22, int(W * 0.016))
    tx0 = x0 + s + gap
    if len(bars) >= 2:
        top_bar_y = min(bars)
        bot_bar_y = max(bars)
        ty0 = max(int(top_bar_y + H * 0.04), int(H * 0.33))
        ty1 = min(int(bot_bar_y - H * 0.05), int(H * 0.60))
    elif len(bars) == 1:
        b = bars[0]
        ty0 = max(int(H * 0.34), int(b - H * 0.22))
        ty1 = min(int(H * 0.58), int(b - H * 0.06))
    else:
        ty0 = int(H * 0.36)
        ty1 = int(H * 0.56)
    if tx1 <= tx0:
        tx1 = tx0 + max(80, int(W * 0.12))
    if ty1 - ty0 < max(40, int(H * 0.065)):
        ty1 = ty0 + max(40, int(H * 0.065))
    return tx0, ty0, tx1, ty1

def _ellipsize(draw, text, font, max_w):
    if not text:
        return ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    lo, hi = 1, len(text)
    best = "..."
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + "..."
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
    os.makedirs("cache", exist_ok=True)
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
        channel = (ch.get("name") or "Youtube").strip() if isinstance(ch, dict) else (ch.strip() if isinstance(ch, str) else "Youtube")
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
        x0, y0, inner_s, left_mask = _detect_left_square(base)
        if left_mask is None or left_mask.size != (inner_s, inner_s):
            radius = max(14, int(inner_s * 0.07))
            left_mask = _rounded_mask(inner_s, radius)
        src = Image.open(raw_path).convert("RGBA")
        reduce_factor = 0.92
        target_h = int(inner_s * reduce_factor)
        target_w = inner_s
        cover = ImageOps.fit(src, (target_w, target_h), method=_resample(), centering=(0.5, 0.5))
        offset_x = (inner_s - target_w) // 2
        offset_y = (inner_s - target_h) // 2
        paste_pos = (x0 + offset_x, y0 + offset_y)
        base.paste(cover, paste_pos, left_mask)
        tx0, ty0, tx1, ty1 = _measure_ui_guides(base, (x0, y0, inner_s))
        text_w = max(1, tx1 - tx0)
        title_font_path = "Opus/assets/font.ttf"
        channel_font_path = "Opus/assets/font2.ttf"
        title_font = _fit_font(draw, title, title_font_path, 64, 28, text_w)
        title_text = _ellipsize(draw, title, title_font, text_w)
        ty0 = int(ty0 + H * 0.01)
        draw.text((tx0, ty0), title_text, fill=(255, 255, 255), font=title_font)
        tb = draw.textbbox((tx0, ty0), title_text, font=title_font)
        ch_y = tb[3] + max(8, int(H * 0.012))
        ch_font = safe_font(channel_font_path, 30)
        ch_text = _ellipsize(draw, channel, ch_font, text_w)
        ch_h = draw.textbbox((0, 0), ch_text, font=ch_font)[3]
        if ch_y + ch_h > ty1:
            ch_y = max(ty0, ty1 - ch_h)
        draw.text((tx0, ch_y), ch_text, fill=(255, 255, 255), font=ch_font)
        base.save(out_path, "PNG")
        try:
            os.remove(raw_path)
        except Exception:
            pass
        return out_path
    except Exception:
        return FAILED
