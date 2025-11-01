import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from Opus import app
from config import FAILED

# --- Constants ---
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# --- Font loader ---
def load_font(path: str, size: int):
    """Safely load font with fallback for multilingual titles."""
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(FALLBACK_FONT, size)


# --- Title wrapping ---
def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2):
    """
    Automatically wrap text to fit within given width.
    Ensures max two lines (for multilingual / long titles).
    """
    words = text.split()
    lines, current_line = [], ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if font.getlength(test_line) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
        if len(lines) >= max_lines:
            break
    if current_line and len(lines) < max_lines:
        lines.append(current_line)
    # Add ellipsis if truncated
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    elif len(words) > 1 and len(lines) == max_lines and " ".join(words) != " ".join(lines):
        lines[-1] += "…"
    return lines[:max_lines]


# --- Main async thumbnail generator ---
async def get_thumb(videoid: str) -> str:
    """
    Generate a cinematic, multilingual thumbnail image (1280x720) for YouTube videos.
    Features:
      - Full blurred background + gradient overlay
      - Left thumbnail with rounded corners and shadow
      - Right side text area (auto-wrapped title + channel info)
      - Progress bar, time display, soft outer shadow
    """
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_cinematic_v6.png")
    if os.path.exists(cache_path):
        return cache_path

    # --- Fetch YouTube data ---
    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        data = (await results.next())["result"][0]
        title = data.get("title", "Unknown Title")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", FAILED)
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        duration = data.get("duration", "Live")
    except Exception:
        title, thumbnail, views, duration = "Unsupported Title", FAILED, "Unknown Views", "Live"

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

    # --- Base and background setup ---
    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = base.filter(ImageFilter.GaussianBlur(25))
    dark_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 180))
    bg = Image.alpha_composite(bg, dark_overlay)

    # --- Outer card shadow ---
    shadow_size = (1280 + 40, 720 + 40)
    outer_shadow = Image.new("RGBA", shadow_size, (0, 0, 0, 0))
    draw_shadow = ImageDraw.Draw(outer_shadow)
    draw_shadow.rounded_rectangle(
        (20, 20, 1260 + 20, 700 + 20),
        radius=40,
        fill=(0, 0, 0, 120),
    )
    outer_shadow = outer_shadow.filter(ImageFilter.GaussianBlur(25))
    full = Image.new("RGBA", shadow_size, (0, 0, 0, 0))
    full.paste(outer_shadow, (0, 0))
    full.paste(bg, (20, 20), bg)
    bg = full.crop((0, 0, 1280, 720))

    draw = ImageDraw.Draw(bg)

    # --- Fonts ---
    title_font = load_font("src/assets/font2.ttf", 40)
    meta_font = load_font("src/assets/font.ttf", 24)
    time_font = load_font("src/assets/font.ttf", 22)

    # --- Left thumbnail ---
    thumb_w, thumb_h = 500, 280
    thumb_x, thumb_y = 90, (720 - thumb_h) // 2
    thumb = base.resize((thumb_w, thumb_h))

    # Shadow for thumb
    shadow = Image.new("RGBA", (thumb_w + 20, thumb_h + 20), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (10, 10, thumb_w + 10, thumb_h + 10), radius=25, fill=(0, 0, 0, 120)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(17))
    bg.paste(shadow, (thumb_x - 10, thumb_y - 10), shadow)

    # Masked thumb
    mask = Image.new("L", (thumb_w, thumb_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, thumb_w, thumb_h), 25, fill=255)
    bg.paste(thumb, (thumb_x, thumb_y), mask)

    # --- Text on right ---
    text_x = thumb_x + thumb_w + 60
    text_max_w = 640
    title_y = thumb_y + 10
    meta_y = title_y + 95

    # Auto-wrap title (supports all languages)
    wrapped_lines = wrap_text(title, title_font, text_max_w, max_lines=2)
    for i, line in enumerate(wrapped_lines):
        draw.text((text_x, title_y + i * 45), line, fill="white", font=title_font)

    # Channel/meta info
    draw.text((text_x, meta_y), f"YouTube • {views}", fill="#DDDDDD", font=meta_font)

    # --- Progress bar ---
    bar_start = text_x
    bar_y = meta_y + 70
    total_len = 550
    red_len = 220
    draw.line([(bar_start, bar_y), (bar_start + red_len, bar_y)], fill="red", width=8)
    draw.line([(bar_start + red_len, bar_y), (bar_start + total_len, bar_y)], fill="#555555", width=6)
    draw.ellipse(
        [(bar_start + red_len - 10, bar_y - 10), (bar_start + red_len + 10, bar_y + 10)],
        fill="red",
    )

    # --- Time text ---
    draw.text((bar_start, bar_y + 15), "00:10", fill="#CCCCCC", font=time_font)
    end_text = "LIVE" if is_live else duration
    end_fill = "red" if is_live else "#CCCCCC"
    draw.text(
        (bar_start + total_len - (90 if is_live else 60), bar_y + 15),
        end_text,
        fill=end_fill,
        font=time_font,
    )

    # --- Save final ---
    bg.save(cache_path)
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    return cache_path
