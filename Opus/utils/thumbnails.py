import os
import re
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter
from youtubesearchpython.__future__ import VideosSearch
from config import FAILED

APPLE_TEMPLATE_PATH = "Opus/assets/apple_music.png"

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

def _most_common_colors(pil_img, n=3, resize=(64, 64)):
    im = pil_img.convert("RGB").resize(resize)
    arr = np.array(im).reshape(-1, 3)
    quant = (arr >> 3) << 3
    tuples = [tuple(c) for c in quant.tolist()]
    unique, counts = np.unique(tuples, axis=0, return_counts=True)
    idx = np.argsort(counts)[::-1]
    colors = [tuple(map(int, unique[i])) for i in idx[:n]]
    return colors or [(120, 120, 120)]

def get_contrasting_color(bg_color):
    lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
    return (30, 30, 30) if lum > 128 else (245, 245, 245)

def _detect_panel_bounds(img_rgba):
    W, H = img_rgba.size
    gray = img_rgba.convert("L")
    arr = np.array(gray)

    thr = int(np.percentile(arr, 90))
    mask = (arr >= thr).astype(np.uint8)

    y0 = int(H * 0.25)
    y1 = int(H * 0.75)
    band = mask[y0:y1, :]

    visited = np.zeros_like(band, dtype=np.uint8)
    best = None
    h, w = band.shape

    def neighbors(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                yield rr, cc

    for r in range(h):
        for c in range(w):
            if band[r, c] and not visited[r, c]:
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
                    for nr, nc in neighbors(rr, cc):
                        if band[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                comp_x_center = (min_c + max_c) / 2
                if best is None or (area > best[0] and comp_x_center > w * 0.5):
                    X0, X1 = min_c, max_c
                    Y0, Y1 = y0 + min_r, y0 + max_r
                    best = (area, X0, X1, Y0, Y1)

    if best is None:
        panel_w = int(W * 0.68)
        panel_h = int(H * 0.36)
        panel_x0 = (W - panel_w) // 2
        panel_x1 = panel_x0 + panel_w
        panel_y0 = (H - panel_h) // 2
        panel_y1 = panel_y0 + panel_h
        return panel_x0, panel_x1, panel_y0, panel_y1

    _, px0, px1, py0, py1 = best
    pad_y = int(H * 0.05)
    py0 = max(0, py0 - pad_y)
    py1 = min(H - 1, py1 + pad_y)
    return px0, px1, py0, py1

def _detect_left_card_bounds(img_rgba):
    W, H = img_rgba.size
    gray = img_rgba.convert("L")
    arr = np.array(gray)

    x_band = int(W * 0.28)
    sub = arr[:, :x_band]

    thr = int(np.percentile(sub, 88))
    mask = (sub >= thr).astype(np.uint8)

    visited = np.zeros_like(mask, dtype=np.uint8)
    best = None
    h, w = mask.shape

    def neighbors(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
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
                    min_c = min(min_c, c)
                    max_c = max(max_c, c)
                    for nr, nc in neighbors(rr, cc):
                        if mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                comp_h = max_r - min_r + 1
                comp_w = max_c - min_c + 1
                if comp_h > comp_w and (best is None or area > best[0]):
                    X0, X1 = min_c, max_c
                    Y0, Y1 = min_r, max_r
                    best = (area, X0, X1, Y0, Y1)

    if best is None:
        card_w = int(W * 0.08)
        card_h = int(H * 0.36)
        x0 = int(W * 0.04)
        x1 = x0 + card_w
        y0 = (H - card_h) // 2
        y1 = y0 + card_h
        return x0, x1, y0, y1

    _, lx0, lx1, ly0, ly1 = best
    return lx0, lx1, ly0, ly1

async def get_thumb(videoid):
    final_path = f"cache/{videoid}.png"
    if os.path.isfile(final_path):
        return final_path

    url = f"https://www.youtube.com/watch?v={videoid}"

    try:
        search = VideosSearch(url, limit=1)
        results = search.result()
        if not results or "result" not in results:
            return FAILED

        r0 = results["result"][0]
        title = re.sub(r"\s+", " ", r0.get("title", "Unknown Title")).strip()
        channel = r0.get("channel", {})
        if isinstance(channel, dict):
            channel = channel.get("name", "Youtube")
        elif not channel:
            channel = "Youtube"

        thumb_field = r0.get("thumbnails") or r0.get("thumbnail") or []
        if isinstance(thumb_field, list) and thumb_field:
            thumbnail_url = thumb_field[0].get("url", FAILED).split("?")[0]
        elif isinstance(thumb_field, dict):
            thumbnail_url = thumb_field.get("url", FAILED).split("?")[0]
        else:
            thumbnail_url = str(thumb_field).split("?")[0] if thumb_field else FAILED

        os.makedirs("cache", exist_ok=True)
        raw_path = f"cache/raw_{videoid}.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    return FAILED
                async with aiofiles.open(raw_path, "wb") as f:
                    await f.write(await resp.read())

        if not os.path.exists(APPLE_TEMPLATE_PATH):
            return FAILED

        base = Image.open(APPLE_TEMPLATE_PATH).convert("RGBA")
        W, H = base.size
        draw = ImageDraw.Draw(base)

        panel_x0, panel_x1, panel_y0, panel_y1 = _detect_panel_bounds(base)
        lx0, lx1, ly0, ly1 = _detect_left_card_bounds(base)
        left_card_h = (ly1 - ly0 + 1)

        GAP = 8
        RADIUS = max(12, left_card_h // 8)
        album_h = int(left_card_h * 1.10)
        album_w = album_h

        album_x = lx0 - 7
        album_y = ly0 - int((album_h - left_card_h) / 2)
        album_x = max(2, min(album_x, W - album_w - 2))
        album_y = max(2, min(album_y, H - album_h - 2))

        src = Image.open(raw_path).convert("RGBA")
        src = ImageEnhance.Color(src).enhance(2.0)
        cover = ImageOps.fit(src, (album_w, album_h), method=_resample_lanczos(), centering=(0.5, 0.5))

        mask = Image.new("L", (album_w, album_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, album_w, album_h), radius=RADIUS, fill=255)
        cover.putalpha(mask)

        shadow = Image.new("RGBA", (album_w + 40, album_h + 40), (0, 0, 0, 0))
        shadow_mask = Image.new("L", (album_w + 40, album_h + 40), 0)
        draw_mask = ImageDraw.Draw(shadow_mask)
        draw_mask.rounded_rectangle(
            (20, 20, album_w + 20, album_h + 20),
            radius=RADIUS,
            fill=180
        )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(10))
        shadow.putalpha(shadow_mask)
        base.paste(shadow, (album_x - 20, album_y - 20), shadow)

        base.paste(cover, (album_x, album_y), cover)

        palette = _most_common_colors(cover)
        fg = (0, 0, 0)
        muted = (120, 120, 120)

        title_font_path = "Opus/assets/font2.ttf"
        meta_font = safe_font("Opus/assets/font.ttf", 22)
        small_font = safe_font("Opus/assets/font.ttf", 22)

        INNER_PAD = 36
        text_x = max(panel_x0 + INNER_PAD, album_x + album_w + GAP)
        text_right = panel_x1 - INNER_PAD
        text_w = max(1, text_right - text_x)
        text_top = panel_y0 + 40

        def shrink_to_fit_one_line(s, start_px, min_px, max_w):
            size = start_px
            while size >= min_px:
                f = safe_font(title_font_path, size)
                w = draw.textbbox((0, 0), s, font=f)[2]
                if w <= max_w:
                    return f
                size -= 1
            return safe_font(title_font_path, min_px)

        def ellipsize_one_line(s, font, max_w):
            if not s:
                return s
            bbox = draw.textbbox((0, 0), s, font=font)
            if (bbox[2] - bbox[0]) <= max_w:
                return s
            lo, hi = 1, len(s)
            best = "…"
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = s[:mid].rstrip() + "…"
                w = draw.textbbox((0, 0), cand, font=font)[2]
                if w <= max_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best

        desired_start = 36
        title_font = shrink_to_fit_one_line(title, desired_start, 24, text_w)
        title_draw = title
        if draw.textbbox((0, 0), title_draw, font=title_font)[2] > text_w:
            title_draw = ellipsize_one_line(title, title_font, text_w)

        draw.text((text_x, text_top), title_draw, fill=fg, font=title_font)
        tb = draw.textbbox((text_x, text_top), title_draw, font=title_font)
        cursor_y = tb[3] + 4

        draw.text((text_x, cursor_y), channel, fill=muted, font=meta_font)
        cb = draw.textbbox((text_x, cursor_y), channel, font=meta_font)
        cursor_y = cb[3] + 28

        bar_h = 6
        bar_bottom_margin = 70
        bar_y0 = min(cursor_y, panel_y1 - bar_bottom_margin)
        bar_x0 = text_x
        bar_x1 = text_right

        draw.rounded_rectangle((bar_x0, bar_y0, bar_x1, bar_y0 + bar_h), radius=3, fill=(220, 220, 220))
        progress = 0.4
        draw.rounded_rectangle(
            (bar_x0, bar_y0, bar_x0 + int((bar_x1 - bar_x0) * progress), bar_y0 + bar_h),
            radius=3,
            fill=palette[0],
        )

        out = base.convert("RGB")
        os.makedirs("cache", exist_ok=True)
        out.save(final_path, "PNG")

        try:
            os.remove(raw_path)
        except Exception:
            pass

        return final_path

    except Exception as e:
        print(f"[get_thumb error] {e}")
        return FAILED
