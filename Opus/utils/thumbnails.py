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
    return Image.Resampling.LANCZOS

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
                min_c = max_c = c  # Fixed: was 'c' instead of 'cc'
                area = 0
                while stack:
                    rr, cc = stack.pop()
                    area += 1
                    min_r = min(min_r, rr)
                    max_r = max(max_r, rr)
                    min_c = min(min_c, cc)  # Fixed
                    max_c = max(max_c, cc)  # Fixed
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
        results = await search.next()
        if not results or "result" not in results or not results["result"]:
            return FAILED
        r0 = results["result"][0]
        title = re.sub(r"\s+", " ", r0.get("title", "Unknown Title")).strip()
        channel = r0.get("channel", {}).get("name", "YouTube") if isinstance(r0.get("channel"), dict) else "YouTube"

        thumb_field = r0.get("thumbnails") or r0.get("thumbnail") or []
        thumbnail_url = ""
        if isinstance(thumb_field, list) and thumb_field:
            thumbnail_url = thumb_field[0].get("url", "").split("?")[0]
        elif isinstance(thumb_field, dict):
            thumbnail_url = thumb_field.get("url", "").split("?")[0]

        if not thumbnail_url:
            return FAILED

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

        # Detect regions
        panel_x0, panel_x1, panel_y0, panel_y1 = _detect_panel_bounds(base)
        lx0, lx1, ly0, ly1 = _detect_left_card_bounds(base)

        left_card_h = ly1 - ly0 + 1
        GAP = 12
        RADIUS = max(16, left_card_h // 7)  # Slightly larger, matches Apple
        album_h = int(left_card_h * 1.15)
        album_w = album_h
        album_x = lx0 - 8
        album_y = ly0 - int((album_h - left_card_h) / 2)
        album_x = max(4, min(album_x, W - album_w - 4))
        album_y = max(4, min(album_y, H - album_h - 4))

        # Load and enhance cover
        src = Image.open(raw_path).convert("RGBA")
        src = ImageEnhance.Color(src).enhance(1.8)  # Slightly less aggressive
        cover = ImageOps.fit(src, (album_w, album_h), method=_resample_lanczos(), centering=(0.5, 0.5))

        # Rounded mask
        mask = Image.new("L", (album_w, album_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, album_w, album_h), radius=RADIUS, fill=255)
        cover.putalpha(mask)

        # Improved shadow
        shadow_size = 48
        shadow = Image.new("RGBA", (album_w + shadow_size, album_h + shadow_size), (0, 0, 0, 0))
        shadow_mask = Image.new("L", (album_w + shadow_size, album_h + shadow_size), 0)
        sm_draw = ImageDraw.Draw(shadow_mask)
        sm_draw.rounded_rectangle(
            (shadow_size//2, shadow_size//2, album_w + shadow_size//2, album_h + shadow_size//2),
            radius=RADIUS,
            fill=160
        )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(14))
        shadow.putalpha(shadow_mask)
        base.paste(shadow, (album_x - shadow_size//2, album_y - shadow_size//2), shadow)

        # Paste cover
        base.paste(cover, (album_x, album_y), cover)

        # Colors
        palette = _most_common_colors(cover, n=1)
        primary_color = palette[0]
        fg = get_contrasting_color(primary_color)
        muted = (140, 140, 140)

        # Fonts
        title_font_path = "Opus/assets/font.ttf"
        artist_font = safe_font("Opus/assets/font2.ttf", 26)
        title_start_size = 40

        # Text layout
        INNER_PAD = 40
        text_x = max(panel_x0 + INNER_PAD, album_x + album_w + GAP)
        text_right = panel_x1 - INNER_PAD
        text_w = max(1, text_right - text_x)
        text_top = panel_y0 + 38

        # Title
        def shrink_to_fit(s, start, min_size, max_w):
            size = start
            while size >= min_size:
                f = safe_font(title_font_path, size)
                w = draw.textbbox((0, 0), s, font=f)[2]
                if w <= max_w:
                    return f
                size -= 1
            return safe_font(title_font_path, min_size)

        title_font = shrink_to_fit(title, title_start_size, 26, text_w)
        title_draw = title
        if draw.textbbox((0, 0), title_draw, font=title_font)[2] > text_w:
            # Ellipsize
            lo, hi = 1, len(title)
            best = "…"
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = title[:mid].rstrip() + "…"
                w = draw.textbbox((0, 0), cand, font=title_font)[2]
                if w <= text_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            title_draw = best

        draw.text((text_x, text_top), title_draw, fill=fg, font=title_font)
        title_bbox = draw.textbbox((text_x, text_top), title_draw, font=title_font)
        cursor_y = title_bbox[3] + 6

        # Artist (channel)
        artist_text = f"{channel} (F..."
        draw.text((text_x, cursor_y), artist_text, fill=muted, font=artist_font)
        artist_bbox = draw.textbbox((text_x, cursor_y), artist_text, font=artist_font)
        cursor_y = artist_bbox[3] + 32

        # Progress bar
        bar_h = 5
        bar_y = panel_y1 - 78
        bar_x0 = text_x
        bar_x1 = text_right
        bar_w = bar_x1 - bar_x0

        # Background bar
        draw.rounded_rectangle((bar_x0, bar_y, bar_x1, bar_y + bar_h), radius=2.5, fill=(200, 200, 200))

        # Progress (30% in your example)
        progress = 0.30
        prog_w = int(bar_w * progress)
        draw.rounded_rectangle(
            (bar_x0, bar_y, bar_x0 + prog_w, bar_y + bar_h),
            radius=2.5,
            fill=primary_color
        )

        # Final output
        out = base.convert("RGB")
        out.save(final_path, "PNG")

        try:
            os.remove(raw_path)
        except Exception:
            pass

        return final_path

    except Exception as e:
        print(f"[get_thumb error] {e}")
        return FAILED
