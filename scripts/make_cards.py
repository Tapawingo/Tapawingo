#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "featured.json"
FONT_PATH = ROOT / "assets" / "fonts" / "BoldPixels.ttf"

OUT_DIR = ROOT / "assets" / "cards"
EMBED_OUT = OUT_DIR / "featured_embed.md"

# Final card size (PNG). The card is drawn on a smaller "pixel canvas" then upscaled with NEAREST.
CARD_W = 1200
CARD_H = 260
SCALE = 2  # pixel size. 2 = finer pixels, 3–4 = chunkier.

# Left logo slot (in BASE pixels, before upscale)
LOGO_SLOT = 72   # square
LOGO_PAD = 16    # padding from left/top in base pixels

# Right text area padding (base pixels)
TEXT_PAD_X = 22

# Ordered dither (4x4 Bayer)
B4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)

# Palette sampled from your hero vibe (sunset + deep navy silhouettes)
C_DARK0 = (8, 16, 64)
C_DARK1 = (14, 22, 68)
C_DARK2 = (34, 38, 87)
C_PURPLE = (83, 61, 123)
C_MAUVE = (128, 75, 129)
C_PINK0 = (228, 117, 131)
C_PINK1 = (249, 134, 130)
C_ORANGE = (250, 176, 119)
C_SUN = (253, 250, 236)

C_TEXT = (245, 245, 245)
C_TEXT_DIM = (220, 220, 235)
C_META = (205, 205, 220)

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def lerp_col(c1: tuple[int,int,int], c2: tuple[int,int,int], t: float) -> tuple[int,int,int]:
    return (int(lerp(c1[0], c2[0], t)), int(lerp(c1[1], c2[1], t)), int(lerp(c1[2], c2[2], t)))

def dither_pick(ca: tuple[int,int,int], cb: tuple[int,int,int], x: int, y: int, amount: float) -> tuple[int,int,int]:
    """Return ca/cb using ordered dither at (x,y), probability `amount` of cb."""
    t = B4[y & 3][x & 3] / 15.0
    return cb if t < max(0.0, min(1.0, amount)) else ca

def clamp_text(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 1)].rstrip() + "…"

def gh_get(url: str, token: str) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def parse_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]

def ridge(base_w: int, base_y: int, amp: int, f1: float, f2: float, phase: float) -> list[int]:
    ys: list[int] = [0] * base_w
    for x in range(base_w):
        n = math.sin(x * f1 + phase) + 0.5 * math.sin(x * f2 + phase * 1.6)
        ys[x] = int(base_y - amp * (0.55 + 0.45 * n))
    return ys

def render_background(base_w: int, base_h: int, seed: int) -> Image.Image:
    # Deterministic “hero-ish” mini landscape
    # (not too busy; leaves room for text)
    import random
    random.seed(seed)

    img = Image.new("RGB", (base_w, base_h), C_DARK0)
    px = img.load()

    hy = int(base_h * 0.56)

    # sky gradient (purple -> pink -> orange)
    for y in range(hy):
        t = y / max(1, hy - 1)
        if t < 0.55:
            c = lerp_col(C_PURPLE, C_PINK0, t / 0.55)
        else:
            c = lerp_col(C_PINK0, C_ORANGE, (t - 0.55) / 0.45)
        for x in range(base_w):
            # subtle texture
            px[x, y] = dither_pick(c, lerp_col(c, (255,255,255), 0.05), x, y, 0.05)

    # clouds (simple pixel streaks)
    for _ in range(16):
        y = random.randrange(8, int(hy * 0.55))
        x0 = random.randrange(0, base_w - 40)
        length = random.randrange(18, 60)
        for i in range(length):
            x = x0 + i
            if 0 <= x < base_w:
                px[x, y] = dither_pick(px[x, y], lerp_col(C_PINK1, C_SUN, 0.25), x, y, 0.35)

    # sun
    sun_x = int(base_w * 0.63)
    sun_y = int(hy * 0.88)
    for y in range(hy):
        for x in range(base_w):
            dx, dy = x - sun_x, y - sun_y
            d = (dx*dx + dy*dy) ** 0.5
            if d < 10:
                px[x, y] = C_SUN
            elif d < 18:
                px[x, y] = lerp_col(C_SUN, C_ORANGE, (d - 10) / 8)
            elif d < 28:
                px[x, y] = dither_pick(px[x, y], C_ORANGE, x, y, 0.10 * (1 - (d - 18) / 10))

    # mountains (two layers)
    far = ridge(base_w, int(hy * 0.96), 10, 0.018, 0.041, 0.8)
    near = ridge(base_w, int(hy * 1.06), 16, 0.014, 0.033, 2.1)

    def fill(layer: list[int], col: tuple[int,int,int], shade: tuple[int,int,int]) -> None:
        for x in range(base_w):
            top = max(0, min(hy - 1, layer[x]))
            for y in range(top, hy):
                # faint dither shading
                px[x, y] = shade if ((x // 6 + y // 6) & 1) == 0 else col

    fill(far, C_MAUVE, lerp_col(C_MAUVE, C_DARK0, 0.18))
    fill(near, C_DARK2, lerp_col(C_DARK2, C_DARK0, 0.18))

    # lake
    for y in range(hy, base_h):
        t = (y - hy) / max(1, (base_h - hy - 1))
        c = lerp_col(lerp_col(C_PINK0, C_PURPLE, 0.6), C_DARK1, min(1.0, t * 1.2))
        for x in range(base_w):
            ripple = 0.05 if (y // 3) % 2 == 0 else 0.0
            px[x, y] = lerp_col(c, (0,0,0), ripple)

    # reflection stripe
    for y in range(hy, base_h):
        t = (y - hy) / max(1, (base_h - hy - 1))
        bw = int(18 * (1 - t) + 6)
        for x in range(max(0, sun_x - bw), min(base_w, sun_x + bw)):
            dx = abs(x - sun_x)
            amt = (1 - dx / max(1, bw)) * (0.28 * (1 - t) + 0.08)
            px[x, y] = dither_pick(px[x, y], C_ORANGE, x, y, amt)

    # foreground silhouette edge (subtle)
    for x in range(base_w):
        yline = int(base_h * 0.74 + 5 * math.sin(x * 0.03) + 3 * math.sin(x * 0.07 + 1.2))
        yline = max(hy + 8, min(base_h - 1, yline))
        for y in range(yline, base_h):
            px[x, y] = C_DARK0

    return img

def load_font(size: int) -> ImageFont.FreeTypeFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    # fallback (won't match perfectly, but won't crash)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", size=size)

def threshold_alpha(im: Image.Image, thresh: int = 120) -> Image.Image:
    """Make text crisp by thresholding alpha channel."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    r, g, b, a = im.split()
    a = a.point(lambda v: 255 if v > thresh else 0)
    return Image.merge("RGBA", (r, g, b, a))

def paste_logo(base: Image.Image, logo_path: Path, x: int, y: int, size: int) -> None:
    """Paste logo into slot with pixelation."""
    draw = ImageDraw.Draw(base)
    slot_rect = (x, y, x + size, y + size)

    # slot background + border
    draw.rounded_rectangle(
        slot_rect,
        radius=6,
        fill=lerp_col(C_DARK2, (0, 0, 0), 0.35),
        outline=(255, 255, 255),
        width=1,
    )

    if not logo_path or not logo_path.is_file():
        for yy in range(y + 6, y + size - 6):
            for xx in range(x + 6, x + size - 6):
                if (xx + yy) % 6 == 0:
                    base.putpixel((xx, yy), lerp_col(C_TEXT_DIM, C_DARK2, 0.65))
        return

    logo = Image.open(logo_path).convert("RGBA")

    pad = 10
    target = size - pad * 2

    down = max(12, target // 2)
    logo_small = logo.resize((down, down), resample=Image.BILINEAR)
    logo_pix = logo_small.resize((target, target), resample=Image.NEAREST)

    ox = x + pad
    oy = y + pad
    base.alpha_composite(logo_pix, (ox, oy))


def render_card(
    repo_name: str,
    subtitle: str,
    description: str,
    language: str,
    stars: int,
    forks: int,
    pushed_at: str,
    logo: str,
    seed: int,
) -> Image.Image:
    base_w, base_h = CARD_W // SCALE, CARD_H // SCALE
    bg = render_background(base_w, base_h, seed).convert("RGBA")

    d = ImageDraw.Draw(bg)

    # logo slot
    lx = LOGO_PAD
    ly = (base_h - LOGO_SLOT) // 2
    logo_path = (ROOT / logo) if (logo and logo.strip()) else None
    paste_logo(bg, logo_path if logo_path else Path("__no_logo__"), lx, ly, LOGO_SLOT)

    # text
    title_font = load_font(22)     # BoldPixels looks good around here at base res
    sub_font = load_font(14)
    meta_font = load_font(12)

    tx = lx + LOGO_SLOT + TEXT_PAD_X
    ty = 34

    # big title
    title = repo_name.upper()
    d.text((tx+1, ty+1), title, font=title_font, fill=(0,0,0,160))
    d.text((tx, ty), title, font=title_font, fill=C_TEXT)

    # subtitle
    sub = (subtitle or "").lower()
    d.text((tx+1, ty+28+1), sub, font=sub_font, fill=(0,0,0,150))
    d.text((tx, ty+28), sub, font=sub_font, fill=C_TEXT_DIM)

    # description (one line, clamped)
    desc = clamp_text((description or "").strip(), 64)
    if desc:
        d.text((tx+1, ty+50+1), desc.lower(), font=sub_font, fill=(0,0,0,120))
        d.text((tx, ty+50), desc.lower(), font=sub_font, fill=lerp_col(C_TEXT_DIM, C_META, 0.35))

    # meta line
    pushed = parse_date(pushed_at)
    meta_bits = []
    if language:
        meta_bits.append(language)
    meta_bits.append(f"★ {stars}")
    meta_bits.append(f"⑂ {forks}")
    if pushed:
        meta_bits.append(f"push {pushed}")
    meta = "  ·  ".join(meta_bits).lower()

    d.text((tx+1, base_h-26+1), meta, font=meta_font, fill=(0,0,0,140))
    d.text((tx, base_h-26), meta, font=meta_font, fill=C_META)

    # crispify text a bit (threshold alpha after composing text)
    bg = threshold_alpha(bg, thresh=120)

    # upscale to final
    out = bg.resize((CARD_W, CARD_H), resample=Image.NEAREST).convert("RGB")
    return out

def main() -> None:
    if not CONFIG.exists():
        raise SystemExit(f"Missing {CONFIG}. Create featured.json first.")
    data = json.loads(CONFIG.read_text(encoding="utf-8"))

    user = data.get("user", "Tapawingo")
    cards = data.get("cards", [])
    if not cards:
        raise SystemExit("featured.json has no cards[]")

    token = os.getenv("GITHUB_TOKEN", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    embed_cells: list[str] = []

    for i, item in enumerate(cards):
        repo = item["repo"]
        href = item.get("href") or f"https://github.com/{user}/{repo}"
        subtitle = item.get("subtitle", "")
        logo = item.get("logo", "")

        info = gh_get(f"https://api.github.com/repos/{user}/{repo}", token)

        repo_name = item.get("title") or info.get("name") or repo
        description = item.get("description") or info.get("description") or ""
        language = info.get("language") or ""
        stars = int(info.get("stargazers_count") or 0)
        forks = int(info.get("forks_count") or 0)
        pushed_at = info.get("pushed_at") or ""

        card = render_card(
            repo_name=repo_name,
            subtitle=subtitle,
            description=description,
            language=language,
            stars=stars,
            forks=forks,
            pushed_at=pushed_at,
            logo=logo,
            seed=100 + i * 13,  # slight variation per card, still cohesive
        )

        out_file = OUT_DIR / f"{repo}.png"
        card.save(out_file, optimize=True)

        cell = f'<a href="{href}"><img src="./assets/cards/{repo}.png" width="100%" alt="{repo} card" /></a>'
        embed_cells.append(cell)

    # write embed snippet (2 columns)
    rows: list[str] = []
    for r in range(0, len(embed_cells), 2):
        left = embed_cells[r]
        right = embed_cells[r + 1] if r + 1 < len(embed_cells) else ""
        rows.append(
            "<tr>\n"
            f'  <td width="50%">{left}</td>\n'
            f'  <td width="50%">{right}</td>\n'
            "</tr>"
        )

    embed_md = "<!-- generated by scripts/make_cards_pixel.py -->\n<table>\n" + "\n".join(rows) + "\n</table>\n"
    EMBED_OUT.write_text(embed_md, encoding="utf-8")

    print(f"Wrote {len(cards)} cards to {OUT_DIR}")
    print(f"Wrote embed snippet to {EMBED_OUT}")

if __name__ == "__main__":
    main()
