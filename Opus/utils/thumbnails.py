import os
import aiofiles
import aiohttp
import asyncio
from functools import partial
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from collections import Counter
from itertools import groupby

# --- Constants ---
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# --- Font Paths ---
PRIMARY_FONT_DIR = "/usr/share/fonts/truetype/josefinsans"
NOTO_FONT_DIR = "/usr/share/fonts/truetype/noto"
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PRIMARY_FONT = FALLBACK_FONT  # DejaVu as main font

# --- Noto Font URLs ---
# --- Noto Font URLs (ALL major Indian + Burmese) ---
NOTO_FONTS = {
    "NotoSans-Regular.ttf":               "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf",

    # Indian scripts
    "NotoSansDevanagari-Regular.ttf":     "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari-Regular.ttf",
    "NotoSansBengali-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/notosansbengali/NotoSansBengali-Regular.ttf",
    "NotoSansGurmukhi-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/notosansgurmukhi/NotoSansGurmukhi-Regular.ttf",
    "NotoSansGujarati-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/notosansgujarati/NotoSansGujarati-Regular.ttf",
    "NotoSansTamil-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/notosanstamil/NotoSansTamil-Regular.ttf",
    "NotoSansTelugu-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/notosanstelugu/NotoSansTelugu-Regular.ttf",
    "NotoSansKannada-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/notosanskannada/NotoSansKannada-Regular.ttf",
    "NotoSansMalayalam-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/notosansmalayalam/NotoSansMalayalam-Regular.ttf",
    "NotoSansOdia-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/notosansodia/NotoSansOdia-Regular.ttf",
    "NotoSansSinhala-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/notosanssinhala/NotoSansSinhala-Regular.ttf",
    "NotoSansMyanmar-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/notosansmyanmar/NotoSansMyanmar-Regular.ttf",
    "NotoSansArabic-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic-Regular.ttf",
    "NotoSansCJKjp-Regular.otf":          "https://github.com/google/fonts/raw/main/ofl/notosanscjk/NotoSansCJKjp-Regular.otf",
}

# Multilingual font priority list
MULTILINGUAL_FONTS = [
    PRIMARY_FONT,
    
    os.path.join(NOTO_FONT_DIR, "NotoSansDevanagari-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansBengali-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansGurmukhi-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansGujarati-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansTamil-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansTelugu-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansKannada-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansMalayalam-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansOdia-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansSinhala-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansMyanmar-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansArabic-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansCJKjp-Regular.otf"),
    os.path.join(NOTO_FONT_DIR, "NotoSans-Regular.ttf"),

    FALLBACK_FONT,
]

# --- Auto-download missing Noto fonts ---
async def ensure_fonts():
    os.makedirs(NOTO_FONT_DIR, exist_ok=True)

    async def download_font(url, path):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path, "wb") as f:
                            await f.write(await resp.read())
        except Exception:
            pass  # Silent fail — fallbacks exist

    for name, url in NOTO_FONTS.items():
        path = os.path.join(NOTO_FONT_DIR, name)
        if not os.path.exists(path):
            await download_font(url, path)


# --- Font loader with fallback ---
def load_font(path_hint: str, size: int):
    font_paths = []
    if path_hint:
        font_paths.append(path_hint)
    font_paths.append(PRIMARY_FONT)
    font_paths.extend(MULTILINGUAL_FONTS)
    seen = set()
    ordered = []
    for p in font_paths:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)

    for p in ordered:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


import unicodedata

def _script_of(char: str) -> str:
    """
    Return the Unicode script name of the first character in `char`.
    Falls back to 'Latin' for ASCII, 'Other' for unknown.
    """
    if len(char) == 0:
        return "Other"
    try:
        # This is the official way: https://docs.python.org/3/library/unicodedata.html#unicodedata.script
        script = unicodedata.script(char[0])
        return script
    except (ValueError, AttributeError):
        # Fallback for very old Python versions or invalid input
        return "Latin" if char[0].isascii() else "Other"

def _split_into_script_runs(text: str):
    def key(c): return _script_of(c)
    for script, chars in groupby(text, key):
        yield script, "".join(chars)

def _best_font_for_text(text: str, size: int) -> ImageFont.FreeTypeFont:
    for fp in MULTILINGUAL_FONTS:
        if not os.path.exists(fp):
            continue
        try:
            font = ImageFont.truetype(fp, size)
            font.getmask(text)  # Raises if glyph missing
            return font
        except Exception:
            continue
    return ImageFont.load_default()


# --- Multilingual text drawing ---
def draw_text_multilingual(draw: ImageDraw.Draw, xy, text: str, base_font_size: int, fill, shadow=True):
    x, y = xy
    if not text:
        return 0

    temp_img = Image.new("RGBA", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    # Try sizes from base down
    for size in range(base_font_size, 12, -2):
        segments = []
        total_w = 0
        for _, seg in _split_into_script_runs(text):
            font = _best_font_for_text(seg, size)
            w = temp_draw.textlength(seg, font=font)
            segments.append((font, seg, w))
            total_w += w
        if total_w <= 640:
            break
    else:
        size = 12
        segments = [( _best_font_for_text(seg, size), seg,
                     temp_draw.textlength(seg, font=_best_font_for_text(seg, size)))
                    for _, seg in _split_into_script_runs(text)]

    cur_x = x
    for font, seg, _ in segments:
        if shadow:
            try:
                draw.text((cur_x + 2, y + 2), seg, font=font, fill=(0, 0, 0, 200))
            except Exception:
                draw.text((cur_x + 2, y + 2), seg, font=font, fill="black")
        draw.text((cur_x, y), seg, font=font, fill=fill)
        cur_x += temp_draw.textlength(seg, font=font)
    return total_w


# --- Dominant color + brightness ---
def get_dominant_color_and_brightness(img: Image.Image):
    small = img.resize((50, 50))
    pixels = [p for p in small.getdata() if len(p) == 3 or (len(p) == 4 and p[3] > 128)]
    if not pixels:
        return (255, 0, 0), "dark"
    r, g, b = Counter(pixels).most_common(1)[0][0][:3]
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    tone = "dark" if brightness < 128 else "light"
    avg = (r + g + b) // 3
    return (int((r + avg) / 2), int((g + avg) / 2), int((b + avg) / 2)), tone


# --- Multilingual-safe wrapping ---
def wrap_text_multilingual(text, font, max_width, max_lines=2, draw=None):
    if draw is None:
        temp = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(temp)

    use_word_split = " " in text.strip()
    lines = []

    if use_word_split:
        words = text.split()
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            width = draw.textlength(candidate, font=font)
            if width <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
    else:
        current = ""
        for ch in text:
            candidate = current + ch
            width = draw.textlength(candidate, font=font)
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = ch
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)

    joined = "".join(lines)
    if len(joined) < len(text) and lines:
        last = lines[-1]
        ellipsis = ".."
        while draw.textlength(last + ellipsis, font=font) > max_width and len(last) > 0:
            last = last[:-1]
        lines[-1] = last + ellipsis if len(last) > 0 else ellipsis

    return lines[:max_lines]


# --- Async blur ---
async def blur_image(img, radius):
    return await asyncio.to_thread(img.filter, ImageFilter.GaussianBlur(radius))


# --- Truncate title ---
def truncate_title(text, max_words=25, max_chars=120, hard_char_limit=25):
    words = text.split()
    if len(words) > max_words or len(text) > max_chars:
        text = " ".join(words[:max_words])[:max_chars].rstrip()
    if len(text) > hard_char_limit:
        text = text[:hard_char_limit].rstrip() + ".."
    return text


# --- Adaptive font size ---
def choose_title_font(text, font_path_hint, max_width, max_lines=2):
    for size in (48, 44, 40, 36, 32, 30, 28, 26, 24):
        f = load_font(font_path_hint, size)
        temp = Image.new("RGBA", (10, 10))
        d = ImageDraw.Draw(temp)
        lines = wrap_text_multilingual(text, f, max_width, max_lines=max_lines, draw=d)
        if len(lines) <= max_lines:
            fits = all(d.textlength(line, font=f) <= max_width for line in lines)
            if fits:
                return f
    return load_font(font_path_hint, 26)


# --- MAIN THUMBNAIL GENERATOR ---
async def get_thumb(videoid: str) -> str:
    await ensure_fonts()

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_cinematic_final.png")
    if os.path.exists(cache_path):
        return cache_path

    # --- Fetch video info ---
    try:
        search = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        result = await search.next()
        data = result["result"][0]
        title = truncate_title(data.get("title", "Unknown Title"))
        thumbnail = data.get("thumbnails", [{}])[0].get("url", FAILED)
        channel = data.get("channel", {}).get("name", "Unknown Channel")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        duration = data.get("duration", "Live")
    except Exception:
        title, thumbnail, channel, views, duration = (
            "Unknown Title", FAILED, "Unknown Channel", "Unknown Views", "Live"
        )

    is_live = str(duration).lower() in {"live", "live now", ""}

    # --- Download thumbnail ---
    thumb_path = os.path.join(CACHE_DIR, f"thumb_{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    return FAILED
    except Exception:
        return FAILED

    # --- Open base image ---
    try:
        base = Image.open(thumb_path).convert("RGBA").resize((1280, 720))
    except Exception:
        return FAILED

    dom_color, tone = get_dominant_color_and_brightness(base)
    text_color = "white" if tone == "dark" else "#222222"
    meta_color = "#DDDDDD" if tone == "dark" else "#333333"

    # --- Background blur & overlays ---
    bg = await blur_image(base, 25)
    dark_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 180 if tone == "dark" else 100))
    bg = Image.alpha_composite(bg, dark_overlay)

    gradient = Image.new("L", (1, 720))
    draw_grad = ImageDraw.Draw(gradient)
    for y in range(720):
        draw_grad.point((0, y), int(255 * (1 - y / 720)))
    alpha = gradient.resize(bg.size)
    black_grad = Image.new("RGBA", bg.size, (0, 0, 0, 120))
    bg = Image.composite(black_grad, bg, alpha)

    # --- Progress bar (drawn early, on top of gradient) ---
    text_x = 90 + 500 + 60
    meta_y = 0  # placeholder, updated later
    bar_y = 0   # placeholder
    total_len = 550
    prog_fraction = 0.35
    prog_len = int(total_len * prog_fraction)
    bar_start = text_x

    # Glow
    glow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=30)
    glow = glow.filter(ImageFilter.GaussianBlur(15))
    bg = Image.alpha_composite(bg, glow)

    draw = ImageDraw.Draw(bg)

    # --- Left thumbnail with shadow & rounded mask ---
    thumb_w, thumb_h = 500, 280
    thumb_x, thumb_y = 90, (720 - thumb_h) // 2
    thumb = base.resize((thumb_w, thumb_h))

    shadow_pad = 20
    shadow = Image.new("RGBA", (thumb_w + shadow_pad, thumb_h + shadow_pad), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (shadow_pad // 2, shadow_pad // 2, thumb_w + shadow_pad // 2, thumb_h + shadow_pad // 2),
        radius=30, fill=(0, 0, 0, 140)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    bg.paste(shadow, (thumb_x - shadow_pad // 2, thumb_y - shadow_pad // 2), shadow)

    mask = Image.new("L", (thumb_w, thumb_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, thumb_w, thumb_h), radius=25, fill=255)
    bg.paste(thumb, (thumb_x, thumb_y), mask)

    # --- Title rendering ---
    title_y = thumb_y + 5
    text_max_w = 640
    title_font = choose_title_font(title, "", text_max_w, max_lines=2)
    wrapped_title = wrap_text_multilingual(title, title_font, text_max_w, max_lines=2, draw=draw)

    title_heights = []
    for line in wrapped_title:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        h = bbox[3] - bbox[1]
        draw_text_multilingual(draw, (text_x, title_y + sum(title_heights)), line,
                               base_font_size=title_font.size, fill=text_color, shadow=True)
        title_heights.append(h + 6)
    title_block_height = sum(title_heights)

    # --- Channel / meta ---
    meta_y = title_y + title_block_height + 5
    meta_text = f"{channel} • {views}"
    draw_text_multilingual(draw, (text_x, meta_y), meta_text,
                           base_font_size=24, fill=meta_color, shadow=True)

    # --- Progress bar (final solid lines) ---
    bar_y = meta_y + 80
    draw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=8)
    draw.line([(bar_start + prog_len, bar_y), (bar_start + total_len, bar_y)], fill="#555555", width=6)
    draw.ellipse(
        [(bar_start + prog_len - 10, bar_y - 10), (bar_start + prog_len + 10, bar_y + 10)],
        fill=dom_color
    )

    # Time stamps
    current_time_text = f"00:{int(prog_fraction * 100):02d}"
    draw_text_multilingual(draw, (bar_start, bar_y + 15), current_time_text,
                           base_font_size=22, fill=meta_color, shadow=True)

    end_text = "LIVE" if is_live else duration
    end_fill = "red" if is_live else meta_color
    tmp_f = load_font("", 22)
    end_width = draw.textbbox((0, 0), end_text, font=tmp_f)[2]
    draw_text_multilingual(draw, (bar_start + total_len - end_width, bar_y + 15), end_text,
                           base_font_size=22, fill=end_fill, shadow=True)

    # --- Save ---
    bg.save(cache_path, "PNG")
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    return cache_path
