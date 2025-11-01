import os
import aiofiles
import aiohttp
import asyncio
from functools import partial
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from collections import Counter
from Opus import app
from config import FAILED

# --- Constants ---
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# --- Font loader ---
def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(FALLBACK_FONT, size)


# --- Dominant color + brightness ---
def get_dominant_color_and_brightness(img: Image.Image):
    small = img.resize((50, 50))
    pixels = small.getdata()
    pixels = [p for p in pixels if len(p) == 3 or (len(p) == 4 and p[3] > 128)]
    if not pixels:
        return (255, 0, 0), "dark"
    common = Counter(pixels).most_common(1)[0][0][:3]
    r, g, b = common
    brightness = (0.299 * r + 0.587 * g + 0.114 * b)
    tone = "dark" if brightness < 128 else "light"
    # Desaturate slightly for progress color
    avg = (r + g + b) // 3
    r, g, b = (int((r + avg) / 2), int((g + avg) / 2), int((b + avg) / 2))
    return (r, g, b), tone


# --- Multilingual-safe wrapping ---
def wrap_text(text, font, max_width, max_lines=2):
    lines, current = [], ""
    for ch in text:
        if font.getlength(current + ch) <= max_width:
            current += ch
        else:
            lines.append(current)
            current = ch
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    joined = "".join(lines)
    if len(joined) < len(text):
        lines[-1] = lines[-1].rstrip() + "…"
    return lines[:max_lines]


# --- Text with soft shadow ---
def draw_text_with_shadow(draw, pos, text, font, fill):
    x, y = pos
    shadow_fill = "black" if fill != "black" else "#CCCCCC"
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_fill)
    draw.text((x, y), text, font=font, fill=fill)


# --- Async helper for CPU-heavy ops ---
async def blur_image(img, radius):
    return await asyncio.to_thread(img.filter, ImageFilter.GaussianBlur(radius))


# --- Main thumbnail generator ---
async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_cinematic_final.png")
    if os.path.exists(cache_path):
        return cache_path

    # --- Fetch video info ---
    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        data = (await results.next())["result"][0]
        title = data.get("title", "Unknown Title")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", FAILED)
        channel = data.get("channel", {}).get("name", "Unknown Channel")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        duration = data.get("duration", "Live")
    except Exception:
        title, thumbnail, channel, views, duration = (
            "Unsupported Title",
            FAILED,
            "Unknown Channel",
            "Unknown Views",
            "Live",
        )

    is_live = duration.lower() in {"live", "live now", ""}

    # --- Download thumbnail ---
    thumb_path = os.path.join(CACHE_DIR, f"thumb_{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
    except Exception:
        return FAILED

    # --- Base image ---
    base = Image.open(thumb_path).convert("RGBA").resize((1280, 720))
    dom_color, tone = get_dominant_color_and_brightness(base)
    text_color = "white" if tone == "dark" else "#222222"
    meta_color = "#DDDDDD" if tone == "dark" else "#333333"

    # --- Background blur & gradient ---
    bg = await blur_image(base, 25)
    dark_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 180 if tone == "dark" else 100))
    bg = Image.alpha_composite(bg, dark_overlay)

    # Gradient overlay for cinematic depth
    gradient = Image.new("L", (1, 720))
    for y in range(720):
        gradient.putpixel((0, y), int(255 * (y / 720)))
    alpha = gradient.resize(bg.size)
    black_grad = Image.new("RGBA", bg.size, (0, 0, 0, 120))
    bg = Image.composite(black_grad, bg, alpha)

    draw = ImageDraw.Draw(bg)

    # --- Fonts ---
    title_font = load_font("src/assets/font2.ttf", 30)
    meta_font = load_font("src/assets/font.ttf", 24)
    time_font = load_font("src/assets/font.ttf", 22)

    # --- Left thumbnail ---
    thumb_w, thumb_h = 500, 280
    thumb_x, thumb_y = 90, (720 - thumb_h) // 2
    thumb = base.resize((thumb_w, thumb_h))

    # Shadow for thumb
    shadow = Image.new("RGBA", (thumb_w + 20, thumb_h + 20), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (10, 10, thumb_w + 10, thumb_h + 10), radius=25, fill=(0, 0, 0, 120)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(15))
    bg.paste(shadow, (thumb_x - 10, thumb_y - 10), shadow)

    # Rounded mask
    mask = Image.new("L", (thumb_w, thumb_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, thumb_w, thumb_h), 25, fill=255)
    bg.paste(thumb, (thumb_x, thumb_y), mask)

    # --- Text placement ---
    text_x = thumb_x + thumb_w + 60
    text_max_w = 640
    title_y = thumb_y + 5

    wrapped_title = wrap_text(title, title_font, text_max_w, max_lines=2)
    title_heights = []
    for i, line in enumerate(wrapped_title):
        _, _, _, h = draw.textbbox((0, 0), line, font=title_font)
        draw_text_with_shadow(draw, (text_x, title_y + sum(title_heights)), line, title_font, text_color)
        title_heights.append(h + 5)
    title_block_height = sum(title_heights)

    meta_y = title_y + title_block_height + 5
    meta_text = f"{channel} • {views}"
    meta_lines = wrap_text(meta_text, meta_font, text_max_w, max_lines=1)
    draw_text_with_shadow(draw, (text_x, meta_y), meta_lines[0], meta_font, meta_color)

    # --- Progress bar with glow ---
    bar_start = text_x
    bar_y = meta_y + 80
    total_len = 550
    prog_len = int(total_len * 0.35)

    # Glow layer
    glow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=30)
    glow = glow.filter(ImageFilter.GaussianBlur(15))
    bg = Image.alpha_composite(bg, glow)

    # Actual progress bar
    draw.line([(bar_start, bar_y), (bar_start + prog_len, bar_y)], fill=dom_color, width=8)
    draw.line([(bar_start + prog_len, bar_y), (bar_start + total_len, bar_y)], fill="#555555", width=6)
    draw.ellipse(
        [(bar_start + prog_len - 10, bar_y - 10), (bar_start + prog_len + 10, bar_y + 10)],
        fill=dom_color,
    )

    # --- Time text ---
    draw_text_with_shadow(draw, (bar_start, bar_y + 15), "00:00", time_font, fill=meta_color)
    end_text = "LIVE" if is_live else duration
    end_fill = "red" if is_live else meta_color
    draw_text_with_shadow(
        draw,
        (bar_start + total_len - (90 if is_live else 60), bar_y + 15),
        end_text,
        time_font,
        fill=end_fill,
    )

    # --- Save final ---
    bg.save(cache_path)
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    return cache_path
