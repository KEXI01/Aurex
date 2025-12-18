import random
from os.path import realpath

import aiohttp
from aiohttp import client_exceptions
from PIL import Image, ImageFilter, ImageDraw

class UnableToFetchCarbon(Exception):
    pass

themes = [
    "3024-night","a11y-dark","blackboard","base16-dark","base16-light","cobalt",
    "duotone-dark","dracula-pro","hopscotch","lucario","material","monokai",
    "nightowl","nord","oceanic-next","one-light","one-dark","panda-syntax",
    "parasio-dark","seti","shades-of-purple","solarized+dark","solarized+light",
    "synthwave-84","twilight","verminal","vscode","yeti","zenburn",
]

colour = [
    "#FF6B6B","#FF9F1C","#FFD166","#06D6A0","#118AB2","#5A189A","#8338EC",
    "#FF4D6D","#00B4D8","#3A86FF","#FF7AB6","#F6C1FF","#BDE0FE","#C1F0C1",
    "#FFC8A2","#FFD8A8","#A0C4FF","#9BF6FF","#F5CAC3","#E2F0CB",
]

class CarbonAPI:
    def __init__(self):
        self.language = "auto"
        self.drop_shadow = True
        self.drop_shadow_blur = "68px"
        self.drop_shadow_offset = "20px"
        self.font_family = "Cascadia Code"
        self.width_adjustment = True
        self.watermark = False

    async def generate(self, text: str, user_id):
        async with aiohttp.ClientSession(headers={"Content-Type": "application/json"}) as ses:
            params = {
                "code": text,
                "theme": random.choice(themes),
                "dropShadow": self.drop_shadow,
                "dropShadowOffsetY": self.drop_shadow_offset,
                "dropShadowBlurRadius": self.drop_shadow_blur,
                "fontFamily": self.font_family,
                "language": self.language,
                "watermark": self.watermark,
                "widthAdjustment": self.width_adjustment,
            }
            try:
                request = await ses.post("https://carbonara.solopov.dev/api/cook", json=params)
            except client_exceptions.ClientConnectorError:
                raise UnableToFetchCarbon("Can not reach the Host!")
            resp = await request.read()
            path = f"cache/carbon{user_id}.jpg"
            with open(path, "wb") as f:
                f.write(resp)
            try:
                img = Image.open(path).convert("RGBA")
                w, h = img.size

                shadow = img.filter(ImageFilter.GaussianBlur(int(min(w, h) * 0.09)))

                def hex_to_rgba(hx, a):
                    hx = hx.lstrip("#")
                    return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), a)

                liquid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(liquid)

                for col in random.sample(colour, 4):
                    cx = random.randint(-w // 3, w + w // 3)
                    cy = random.randint(-h // 3, h + h // 3)
                    rw = random.randint(int(w * 0.9), int(w * 1.4))
                    rh = random.randint(int(h * 0.8), int(h * 1.3))
                    draw.ellipse(
                        [cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2],
                        fill=hex_to_rgba(col, random.randint(180, 240)),
                    )

                liquid = liquid.filter(ImageFilter.GaussianBlur(int(min(w, h) * 0.18)))
                base = Image.alpha_composite(shadow, liquid)

                panel_w = int(w * 0.92)
                panel_h = int(h * 0.62)
                left = (w - panel_w) // 2
                top = int(h * 0.12)
                right = left + panel_w
                bottom = top + panel_h

                frost = base.crop((left, top, right, bottom)).filter(
                    ImageFilter.GaussianBlur(int(min(w, h) * 0.06))
                )
                panel = img.crop((left, top, right, bottom)).convert("RGBA")
                frost = Image.alpha_composite(frost, panel)

                mask = Image.new("L", (panel_w, panel_h), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    [0, 0, panel_w, panel_h],
                    radius=int(min(panel_w, panel_h) * 0.06),
                    fill=255,
                )

                base.paste(frost, (left, top), mask)

                glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(glow)
                gdraw.rounded_rectangle(
                    [left, top, right, bottom],
                    radius=int(min(panel_w, panel_h) * 0.06),
                    outline=(255, 255, 255, 55),
                    width=2,
                )

                final = Image.alpha_composite(base, glow).convert("RGB")
                final.save(path, "JPEG", quality=90, subsampling=1)
            except Exception:
                pass
            return realpath(path)
