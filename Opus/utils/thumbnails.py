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
                    min_r = min(min_r, rr)
                    max_r = max(max_r, rr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
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
        return x0, y0, s, None
    _, x0, y0, x1, y1 = best
    x0 += margin
    y0 += margin
    x1 += margin
    y1 += margin
    s = min(x1 - x0 + 1, y1 - y0 + 1)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    half = s // 2
    sx0 = max(0, min(cx - half, W - s))
    sy0 = max(0, min(cy - half, H - s))
    inset = max(10, int(min(W, H) * 0.008))
    m = Image.new("L", (s - inset * 2, s - inset * 2), 0)
    rad = max(14, int((s - inset * 2) * 0.08))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.size[0], m.size[1]), radius=rad, fill=255)
    return sx0 + inset, sy0 + inset, s - inset * 2, m

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
    col_centers = _find_bright_rows_cols(right, axis=1, frac=0.6, smooth=9)
    if col_centers.size:
        icon_col = int(col_centers.max())
        tx1 = rx0 + icon_col - max(22, int(W * 0.02))
    else:
        tx1 = int(W * 0.88)
    x0, y0, s = thumb_box
    gap = max(24, int(W * 0.018))
    tx0 = x0 + s + gap
    if len(bars) >= 2:
        top_bar_y = min(bars)
        bot_bar_y = max(bars)
        ty0 = max(int(top_bar_y + H * 0.035), int(H * 0.34))
        ty1 = min(int(bot_bar_y - H * 0.045), int(H * 0.60))
    elif len(bars) == 1:
        b = bars[0]
        ty0 = max(int(H * 0.34), int(b - H * 0.22))
        ty1 = min(int(H * 0.58), int(b - H * 0.06))
    else:
        ty0 = int(H * 0.36)
        ty1 = int(H * 0.56)
    if tx1 <= tx0:
        tx1 = tx0 + max(90, int(W * 0.14))
    if ty1 - ty0 < max(40, int(H * 0.065)):
        ty1 = ty0 + max(40, int(H * 0.065))
    ty0 += int(H * 0.01)
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

def _fit_with_extra_chars(draw, text, path, base_px, min_px, max_w, extra_chars=7):
    f0 = safe_font(path, base_px)
    t0 = _ellipsize(draw, text, f0, max_w)
    plain_len = len(t0.replace("…", ""))
    target_len = min(len(text), plain_len + max(0, extra_chars))
    for s in range(base_px, max(min_px, base_px - 6), -1):
        f = safe_font(path, s)
        cand = text[:target_len] + ("" if target_len == len(text) else "…")
        if draw.textbbox((0, 0), cand, font=f)[2] <= max_w:
            return f, cand
    f = _fit_font(draw, text, path, base_px, min_px, max_w)
    return f, _ellipsize(draw, text, f, max_w)

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

        x0, y0, s, left_mask = _detect_left_square(base)

        src = Image.open(raw_path).convert("RGBA")

        scale = 0.96
        rs = max(2, int(s * scale))
        cover = ImageOps.fit(src, (rs, rs), method=_resample(), centering=(0.5, 0.5))

        canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        off_x = (s - rs) // 2 - int(s * 0.02)
        off_y = (s - rs) // 2 + int(s * 0.03)
        off_x = max(0, min(off_x, s - rs))
        off_y = max(0, min(off_y, s - rs))
        canvas.paste(cover, (off_x, off_y))

        if left_mask is None:
            mask = Image.new("L", (s, s), 0)
            rad = max(14, int(s * 0.08))
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, s, s), radius=rad, fill=255)
        else:
            mask = left_mask
        if mask.size != (s, s):
            tmp = Image.new("L", (s, s), 0)
            off = ((s - mask.size[0]) // 2, (s - mask.size[1]) // 2)
            tmp.paste(mask, off)
            mask = tmp

        base.paste(canvas, (x0, y0), mask)

        tx0, ty0, tx1, ty1 = _measure_ui_guides(base, (x0, y0, s))
        text_w = max(1, tx1 - tx0)

        title_font_path = "Opus/assets/font.ttf"
        channel_font_path = "Opus/assets/font2.ttf"

        title_font, title_text = _fit_with_extra_chars(draw, title, title_font_path, 56, 26, text_w, extra_chars=7)
        draw.text((tx0, ty0), title_text, fill=(255, 255, 255), font=title_font)

        tb = draw.textbbox((tx0, ty0), title_text, font=title_font)
        ch_y = tb[3] + max(6, int(H * 0.01))

        ch_font_base = 30
        ch_font_min = 24
        ch_font, ch_text = _fit_with_extra_chars(draw, channel, channel_font_path, ch_font_base, ch_font_min, text_w, extra_chars=7)

        ch_h = draw.textbbox((0, 0), ch_text, font=ch_font)[3]
        if ch_y + ch_h > ty1:
            ch_y = max(ty0, ty1 - ch_h)

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
