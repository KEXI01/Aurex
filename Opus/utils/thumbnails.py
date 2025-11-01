import os
import aiofiles
import aiohttp
import asyncio
from functools import partial
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from collections import Counter
from config import FAILED

# --- Constants ---
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# --- Font Paths ---
PRIMARY_FONT_DIR = "/usr/share/fonts/truetype/josefinsans"
NOTO_FONT_DIR = "/usr/share/fonts/truetype/noto"
PRIMARY_FONT = os.path.join(PRIMARY_FONT_DIR, "JosefinSans-Regular.ttf")
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# --- Noto Font URLs (broad Unicode coverage) ---
NOTO_FONTS = {
    "NotoSans-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf",
    "NotoSansDevanagari-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari-Regular.ttf",
    "NotoSansArabic-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic-Regular.ttf",
    "NotoSansCJK-Regular.ttc": "https://github.com/google/fonts/raw/main/ofl/notosanscjkjp/NotoSansCJKjp-Regular.otf",
}

# List of fonts to try
MULTILINGUAL_FONTS = [
    os.path.join(NOTO_FONT_DIR, "NotoSans-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansDevanagari-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansArabic-Regular.ttf"),
    os.path.join(NOTO_FONT_DIR, "NotoSansCJK-Regular.ttc"),
    FALLBACK_FONT,
]


# --- Auto-download fonts if missing ---
async def ensure_fonts():
    os.makedirs(PRIMARY_FONT_DIR, exist_ok=True)
    os.makedirs(NOTO_FONT_DIR, exist_ok=True)

    async def download_font(url, path):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path, "wb") as f:
                            await f.write(await resp.read())
        except Exception:
            pass

    # Download Josefin Sans if missing
    if not os.path.exists(PRIMARY_FONT):
        await download_font(
            "https://github.com/google/fonts/raw/main/ofl/josefinsans/JosefinSans-Regular.ttf",
            PRIMARY_FONT,
        )

    # Download Noto fonts if missing
    for name, url in NOTO_FONTS.items():
        path = os.path.join(NOTO_FONT_DIR, name)
        if not os.path.exists(path):
            await download_font(url, path)


# --- Font loader (multilingual safe) ---
def load_font(path_hint: str, size: int):
    font_paths = [PRIMARY_FONT]
    if path_hint:
        font_paths.append(path_hint)
    font_paths.extend(MULTILINGUAL_FONTS)

    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# --- Dominant color + brightness ---
def get_dominant_color_and_brightness(img: Image.Image):
    small = img.resize((50, 50))
    pixels = [p for p in small.getdata() if len(p) == 3 or (len(p) == 4 and p[3] > 128)]
    if not pixels:
        return (255, 0, 0), "dark"
    r, g, b = Counter(pixels).most_common(1)[0][0][:3]
    brightness = (0.299 * r + 0.587 * g + 0.114 * b)
    tone = "dark" if brightness < 128 else "light"
    avg = (r + g + b) // 3
    return (int((r + avg) / 2), int((g + avg) / 2), int((b + avg) / 2)), tone


# --- Multilingual-safe wrapping ---
def wrap_text_multilingual(text, font, max_width, max_lines=2, draw=None):
    if draw is None:
        temp = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(temp)

    lines, current = [], ""
    for ch in text:
        test_line = current + ch
        width = draw.textlength(test_line, font=font)
        if width <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = ch
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    # Ellipsis if truncated
    if len(lines) == max_lines and len("".join(lines)) < len(text):
        last = lines[-1]
        ellipsis = "…"
        while draw.textlength(last + ellipsis, font=font) > max_width and last:
            last = last[:-1]
        lines[-1] = last + ellipsis

    return lines[:max_lines]


# --- Text with soft shadow ---
def draw_text_with_shadow(draw, pos, text, font, fill):
    x, y = pos
    shadow_col = (0, 0, 0, 200)
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_col)
    draw.text((x, y), text, font=font, fill=fill)


# --- Async helper for CPU-heavy ops ---
async def blur_image(img, radius):
    return await asyncio.to_thread(img.filter, ImageFilter.GaussianBlur(radius))


# --- Truncate title if too long ---
def truncate_title(text, max_words=25, max_chars=120, hard_char_limit=25):
    words = text.split()
    if len(words) > max_words or len(text) > max_chars:
        text = " ".join(words[:max_words])[:max_chars].rstrip()
    if len(text) > hard_char_limit:
        text = text[:hard_char_limit].rstrip() + ".."
    return text


# --- Adaptive multilingual font size ---
def choose_title_font(text, font_path_hint, max_width, max_lines=2):
    for size in (48, 44, 40, 36, 32, 30, 28, 26, 24):
        f = load_font(font_path_hint, size)
        temp = Image.new("RGBA", (10, 10))
        d = ImageDraw.Draw(temp)
        lines = wrap_text_multilingual(text, f, max_width, max_lines=max_lines, draw=d)
        if len(lines) <= max_lines:
            return f
    return load_font(font_path_hint, 26)


# --- Main thumbnail generator ---
async def get_thumb(videoid: str) -> str:
    await ensure_fonts()

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_cinematic_final.png")
    if os.path.exists(cache_path):
        return cache_path

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
            "Unknown Title",
            FAILED,
            "Unknown Channel",
            "Unknown Views",
            "Live",
        )

    is_live = str(duration).lower() in {"live", "live now", ""}

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

    try:
        base = Image.open(thumb_path).convert("RGBA").resize((1280, 720))
    except Exception:
        return FAILED

    dom_color, tone = get_dominant_color_and_brightness(base)
    text_color = "white" if tone == "dark" else "#222222"
    meta_color = "#DDDDDD" if tone == "dark" else "#333333"

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

    draw = ImageDraw.Draw(bg)

    text_x = 90 + 500 + 60
    text_max_w = 640
    title_font = choose_title_font(title, "", text_max_w, max_lines=2)
    meta_font = load_font("", 24)
    time_font = load_font("", 22)

    thumb_w, thumb_h = 500, 280
    thumb_x, thumb_y = 90, (720 - thumb_h) // 2
    thumb = base.resize((thumb_w, thumb_h))

    shadow_pad = 20
    shadow = Image.new("RGBA", (thumb_w + shadow_pad, thumb_h + shadow_pad), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (shadow_pad // 2, shadow_pad // 2, thumb_w + shadow_pad // 2, thumb_h + shadow_pad // 2),
        radius=30,
        fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    bg.paste(shadow, (thumb_x - shadow_pad // 2, thumb_y - shadow_pad // 2), shadow)

    mask = Image.new("L", (thumb_w, thumb_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, thumb_w, thumb_h), radius=25, fill=255)
    bg.paste(thumb, (thumb_x, thumb_y), mask)

    title_y = thumb_y + 5
    wrapped_title = wrap_text_multilingual(title, title_font, text_max_w, max_lines=2, draw=draw)
    total_height = 0
    for line in wrapped_title:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        draw_text_with_shadow(draw, (text_x, title_y + total_height), line, title_font, text_color)
        total_height += bbox[3] - bbox[1] + 6

    meta_y = title_y + total_height + 5
    meta_text = f"{channel} • {views}"
    draw_text_with_shadow(draw, (text_x, meta_y), meta_text, meta_font, meta_color)

    bar_start = text_x
    bar_y = meta_y + 80
    total_len = 550
    prog_fraction = 0.35
    prog_len = int(total_len * prog_fraction)

    glow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=30)
    glow = glow.filter(ImageFilter.GaussianBlur(15))
    bg = Image.alpha_composite(bg, glow)

    draw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=8)
    draw.line([(bar_start + prog_len, bar_y), (bar_start + total_len, bar_y)], fill="#555555", width=6)
    draw.ellipse([(bar_start + prog_len - 10, bar_y - 10), (bar_start + prog_len + 10, bar_y + 10)], fill=dom_color)

    current_time_text = f"00:{int(prog_fraction * 100):02d}"
    draw_text_with_shadow(draw, (bar_start, bar_y + 15), current_time_text, time_font, meta_color)
    end_text = "LIVE" if is_live else duration
    end_fill = "red" if is_live else meta_color
    end_width = draw.textbbox((0, 0), end_text, font=time_font)[2]
    draw_text_with_shadow(draw, (bar_start + total_len - end_width, bar_y + 15), end_text, time_font, end_fill)

    bg.save(cache_path, "PNG")
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    return cache_path
