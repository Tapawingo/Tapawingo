#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "featured.json"
OUT_DIR = ROOT / "assets" / "cards"
EMBED_OUT = OUT_DIR / "featured_embed.md"

CARD_W = 560
CARD_H = 170
PADDING = 22

FONT = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"

def gh_get(url: str, token: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )

def clamp_mono(text: str, width_chars: int, max_lines: int) -> list[str]:
    # Simple character-based wrap for monospace rendering.
    text = (text or "").strip()
    if not text:
        return []
    wrapped = textwrap.wrap(text, width=width_chars, break_long_words=False, break_on_hyphens=False)
    if len(wrapped) <= max_lines:
        return wrapped
    kept = wrapped[:max_lines]
    # add ellipsis to last line if truncated
    if len(kept[-1]) >= 1:
        kept[-1] = (kept[-1][: max(0, width_chars - 1)] + "…").rstrip()
    return kept

def make_card_svg(
    name: str,
    subtitle: str,
    description: str,
    language: str,
    stars: int,
    forks: int,
    pushed_at: str,
) -> str:
    # approximate text layout
    title_size = 26
    sub_size = 14
    body_size = 14
    meta_size = 13

    # character widths (mono-ish). tune to taste.
    body_chars = 62

    desc_lines = clamp_mono(description, width_chars=body_chars, max_lines=2)

    pushed_date = ""
    if pushed_at:
        try:
            pushed_date = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            pushed_date = pushed_at[:10]

    meta_parts = []
    if language:
        meta_parts.append(language)
    meta_parts.append(f"★ {stars}")
    meta_parts.append(f"⑂ {forks}")
    if pushed_date:
        meta_parts.append(f"push {pushed_date}")
    meta = "  ·  ".join(meta_parts)

    # vertical positions
    x = PADDING
    y0 = 46
    y_sub = y0 + 26
    y_desc1 = y_sub + 30
    y_desc2 = y_desc1 + 18
    y_meta = CARD_H - 26

    desc_svg = ""
    if len(desc_lines) >= 1:
        desc_svg += f'<text x="{x}" y="{y_desc1}" fill="#D6D6D6" font-size="{body_size}">{esc(desc_lines[0])}</text>'
    if len(desc_lines) >= 2:
        desc_svg += f'<text x="{x}" y="{y_desc2}" fill="#D6D6D6" font-size="{body_size}">{esc(desc_lines[1])}</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{CARD_H}" viewBox="0 0 {CARD_W} {CARD_H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#050505"/>
      <stop offset="1" stop-color="#0B0B0B"/>
    </linearGradient>

    <pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse">
      <rect width="6" height="6" fill="transparent"/>
      <rect y="0" width="6" height="1" fill="#FFFFFF" opacity="0.05"/>
    </pattern>

    <!-- dither patterns -->
    <pattern id="ditherA" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="transparent"/>
      <rect x="1" y="1" width="1" height="1" fill="#fff" opacity="0.22"/>
      <rect x="5" y="2" width="1" height="1" fill="#fff" opacity="0.22"/>
      <rect x="3" y="4" width="1" height="1" fill="#fff" opacity="0.22"/>
      <rect x="7" y="6" width="1" height="1" fill="#fff" opacity="0.22"/>
      <rect x="2" y="7" width="1" height="1" fill="#fff" opacity="0.22"/>
    </pattern>

    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="1.2" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect width="{CARD_W}" height="{CARD_H}" rx="18" fill="url(#bg)"/>
  <rect width="{CARD_W}" height="{CARD_H}" rx="18" fill="url(#scan)" opacity="0.65"/>

  <!-- dither corner mark -->
  <rect x="{CARD_W-120}" y="18" width="92" height="22" rx="6" fill="url(#ditherA)" opacity="0.95"/>
  <text x="{CARD_W-74}" y="34" text-anchor="middle" fill="#0B0B0B" font-size="12"
        font-family="{FONT}" opacity="0.85">FEATURED</text>

  <rect x="14" y="14" width="{CARD_W-28}" height="{CARD_H-28}" rx="14"
        fill="rgba(0,0,0,0.30)" stroke="rgba(255,255,255,0.16)"/>

  <g font-family="{FONT}">
    <text x="{x}" y="{y0}" fill="#FFFFFF" font-size="{title_size}" filter="url(#softGlow)">{esc(name)}</text>
    <text x="{x}" y="{y_sub}" fill="#BDBDBD" font-size="{sub_size}">{esc(subtitle)}</text>

    {desc_svg}

    <text x="{x}" y="{y_meta}" fill="#AFAFAF" font-size="{meta_size}">{esc(meta)}</text>
  </g>

  <!-- dither underline -->
  <rect x="{x}" y="{CARD_H-18}" width="220" height="8" fill="url(#ditherA)" opacity="0.9"/>
</svg>
'''
    return svg

def main() -> None:
    if not CONFIG.exists():
        raise SystemExit(f"Missing {CONFIG}. Create featured.json first.")

    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    user = data.get("user") or "Tapawingo"
    cards = data.get("cards") or []
    if not cards:
        raise SystemExit("featured.json has no cards[]")

    token = os.getenv("GITHUB_TOKEN", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    embed_cells = []
    for i, item in enumerate(cards):
        repo = item["repo"]
        href = item.get("href") or f"https://github.com/{user}/{repo}"
        subtitle = item.get("subtitle") or ""

        info = gh_get(f"https://api.github.com/repos/{user}/{repo}", token)
        name = item.get("title") or info.get("name") or repo
        description = item.get("description") or info.get("description") or ""
        language = info.get("language") or ""
        stars = int(info.get("stargazers_count") or 0)
        forks = int(info.get("forks_count") or 0)
        pushed_at = info.get("pushed_at") or ""

        svg = make_card_svg(
            name=name,
            subtitle=subtitle,
            description=description,
            language=language,
            stars=stars,
            forks=forks,
            pushed_at=pushed_at,
        )

        out_file = OUT_DIR / f"{repo}.svg"
        out_file.write_text(svg, encoding="utf-8")

        # embed cell (2 columns)
        cell = f'<a href="{href}"><img src="./assets/cards/{repo}.svg" width="100%" alt="{repo} card" /></a>'
        embed_cells.append(cell)

    # write a ready-to-copy embed snippet (2 columns)
    rows = []
    for r in range(0, len(embed_cells), 2):
        left = embed_cells[r]
        right = embed_cells[r + 1] if r + 1 < len(embed_cells) else ""
        row = (
            "<tr>\n"
            f'  <td width="50%">{left}</td>\n'
            f'  <td width="50%">{right}</td>\n'
            "</tr>"
        )
        rows.append(row)

    embed_md = "<!-- generated by scripts/make_cards.py -->\n<table>\n" + "\n".join(rows) + "\n</table>\n"
    EMBED_OUT.write_text(embed_md, encoding="utf-8")

    print(f"Wrote {len(cards)} cards to {OUT_DIR}")
    print(f"Wrote embed snippet to {EMBED_OUT}")

if __name__ == "__main__":
    main()
