#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

import requests


@dataclass
class CardSpec:
    repo: str
    subtitle: str = ""
    href: str = ""
    logo: str = ""
    title: str = ""
    description: str = ""


def gh_get(url: str, token: str) -> Optional[Any]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code in (403, 404):
        return None
    r.raise_for_status()
    return r.json()


def parse_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = (lines[-1][: max(0, max_chars - 1)].rstrip() + "…")
    return lines[:max_lines]


def guess_mime_from_ext(ext: str) -> Optional[str]:
    ext = ext.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(ext)


def file_to_data_uri(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    mime = guess_mime_from_ext(path.suffix)
    if not mime:
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def normalize_github_blob_url(url: str) -> str:
    if "github.com/" in url and "/blob/" in url and "raw=" not in url:
        return url + ("&raw=1" if "?" in url else "?raw=1")
    return url


def url_to_data_uri(url: str) -> Optional[str]:
    url = normalize_github_blob_url(url)
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not ctype:
            path = urlparse(url).path
            ctype = guess_mime_from_ext(Path(path).suffix) or "application/octet-stream"
        b64 = base64.b64encode(r.content).decode("ascii")
        return f"data:{ctype};base64,{b64}"
    except Exception:
        return None


def logo_to_data_uri(logo: str, root: Path) -> Optional[str]:
    s = (logo or "").strip()
    if not s:
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return url_to_data_uri(s)
    return file_to_data_uri((root / s).resolve())


def parse_owner_repo_from_href(href: str) -> Optional[Tuple[str, str]]:
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", href)
    if not m:
        return None
    return m.group(1), m.group(2)


def get_owner_repo(default_user: str, card: CardSpec) -> Tuple[str, str]:
    r = (card.repo or "").strip()
    if "/" in r:
        owner, repo = r.split("/", 1)
        return owner, repo
    from_href = parse_owner_repo_from_href(card.href or "")
    if from_href:
        return from_href
    return default_user, r


def render_card_svg(
    *,
    width: int,
    height: int,
    name: str,
    subtitle: str,
    description: str,
    language: str,
    stars: int,
    forks: int,
    pushed: str,
    href: str,
    logo_data_uri: Optional[str],
) -> str:
    pad = 18
    logo = 96
    logo_inset = 00
    gap = 18
    x_text = pad + logo + gap

    title_y = 56 + 20
    sub_y = 102 + 20
    desc_y1 = 102
    desc_y2 = 120
    meta_y = 144

    desc_lines = wrap(description, max_chars=74, max_lines=2)
    sub_line = (subtitle or "").strip()
    pushed_line = f"Updated {pushed}" if pushed else ""

    meta_bits = []
    if language:
        meta_bits.append(language)
    if stars or forks:
        meta_bits.append(f"★ {stars}")
        meta_bits.append(f"⑂ {forks}")
    if pushed_line:
        meta_bits.append(pushed_line)
    meta = " · ".join(meta_bits)

    name_e = escape(name)
    sub_e = escape(sub_line)
    d1 = escape(desc_lines[0]) if len(desc_lines) > 0 else ""
    d2 = escape(desc_lines[1]) if len(desc_lines) > 1 else ""
    meta_e = escape(meta)

    logo_y = (height - logo) // 2

    if logo_data_uri:
        logo_block = f"""
  <g>
    <rect x="{pad}" y="{logo_y}" width="{logo}" height="{logo}" rx="2" class="logoBg"/>
    <clipPath id="clip">
      <rect x="{pad}" y="{logo_y}" width="{logo}" height="{logo}" rx="2"/>
    </clipPath>
    <image href="{logo_data_uri}" x="{pad + logo_inset}" y="{logo_y + logo_inset}" width="{logo - 2*logo_inset}" height="{logo - 2*logo_inset}"
           clip-path="url(#clip)" preserveAspectRatio="xMidYMid slice"/>
    <rect x="{pad}" y="{logo_y}" width="{logo}" height="{logo}" rx="2" class="logoStroke"/>
  </g>
"""
    else:
        cx = pad + logo // 2
        cy = height // 2
        logo_block = f"""
  <g>
    <rect x="{pad}" y="{logo_y}" width="{logo}" height="{logo}" rx="2" class="logoBg"/>
    <circle cx="{cx}" cy="{cy}" r="26" class="logoRing"/>
    <path d="M{cx-18},{cy-6} h36 v12 h-36 z" class="logoMark"/>
    <rect x="{pad}" y="{logo_y}" width="{logo}" height="{logo}" rx="2" class="logoStroke"/>
  </g>
"""

    link_start = f'<a href="{escape(href)}" target="_blank" rel="noreferrer">' if href else ""
    link_end = "</a>" if href else ""

    sub_svg = f'<text x="{x_text}" y="{sub_y}" class="subtitle">{sub_e}</text>' if sub_line else ""
    d1_svg = f'<text x="{x_text}" y="{desc_y1}" class="desc">{d1}</text>' if d1 else ""
    d2_svg = f'<text x="{x_text}" y="{desc_y2}" class="desc">{d2}</text>' if d2 else ""
    meta_svg = f'<text x="{x_text}" y="{meta_y}" class="meta">{meta_e}</text>' if meta_e else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="{name_e}">
  <style>
    :root {{
      --bg: transparent;
      --border: #d0d7de;
      --text: #0366d6;
      --title: #0366d6;
      --muted: #57606a;
      --subtle: #f6f8fa;
      --ring: #afb8c1;
      --mark: #57606a;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: transparent;
        --border: #30363d;
        --text: #0366d6;
        --title: #0366d6;
        --muted: #8b949e;
        --subtle: #161b22;
        --ring: #30363d;
        --mark: #8b949e;
      }}
    }}
    .card {{ fill: var(--bg); stroke: var(--border); stroke-width: 2; }}
    .title {{ fill: var(--title); font: 700 42px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji; }}
    .subtitle {{ fill: var(--muted); font: 400 32px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji; }}
    .desc {{ fill: var(--muted); font: 400 31px ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .meta {{ fill: var(--muted); font: 400 30px ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .logoBg {{ fill: transparent; }}
    .logoStroke {{ fill: none; stroke: transparent; }}
    .logoRing {{ fill: none; stroke: var(--ring); stroke-width: 2; }}
    .logoMark {{ fill: var(--mark); opacity: 0.9; }}
  </style>

  {link_start}
  <rect x="1" y="1" width="{width-2}" height="{height-2}" rx="0" class="card"/>
  {logo_block}
  <text x="{x_text}" y="{title_y}" class="title">{name_e}</text>
  {sub_svg}
  {d1_svg}
  {d2_svg}
  {meta_svg}
  {link_end}
</svg>"""


def load_config(path: Path) -> tuple[str, list[CardSpec]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    user = (data.get("user") or "").strip() or "Tapawingo"
    cards_raw = data.get("cards") or []
    cards: list[CardSpec] = []
    for c in cards_raw:
        cards.append(
            CardSpec(
                repo=(c.get("repo") or "").strip(),
                subtitle=c.get("subtitle", "") or "",
                href=c.get("href", "") or "",
                logo=c.get("logo", "") or "",
                title=c.get("title", "") or "",
                description=c.get("description", "") or "",
            )
        )
    return user, [c for c in cards if c.repo or c.href]


def slug_for(card: CardSpec, default_user: str) -> str:
    owner, repo = get_owner_repo(default_user, card)
    return f"{owner}__{repo}".replace("/", "__")


def write_embed(cards: list[CardSpec], default_user: str, out_dir: Path) -> None:
    cells = []
    for c in cards:
        owner, repo = get_owner_repo(default_user, c)
        href = c.href or f"https://github.com/{owner}/{repo}"
        slug = slug_for(c, default_user)
        cells.append(
            f'<a href="{href}"><img src="./assets/cards/{slug}.svg" width="100%" alt="{owner}/{repo} card" /></a>'
        )
    rows = []
    for i in range(0, len(cells), 2):
        left = cells[i]
        right = cells[i + 1] if i + 1 < len(cells) else ""
        rows.append(
            "<tr>\n"
            f'  <td width="50%">{left}</td>\n'
            f'  <td width="50%">{right}</td>\n'
            "</tr>"
        )
    embed = "<!-- generated by scripts/make_cards.py -->\n<table>\n" + "\n".join(rows) + "\n</table>\n"
    (out_dir / "featured_embed.md").write_text(embed, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="featured.json")
    ap.add_argument("--out-dir", default="assets/cards")
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--height", type=int, default=170)
    ap.add_argument("--user", default="")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    config = root / args.config
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    user_cfg, cards = load_config(config)
    default_user = (args.user or user_cfg).strip() or "Tapawingo"
    token = os.getenv("GITHUB_TOKEN", "")

    for c in cards:
        owner, repo = get_owner_repo(default_user, c)
        info = gh_get(f"https://api.github.com/repos/{owner}/{repo}", token)
        if info is None and repo.lower() != repo:
            info = gh_get(f"https://api.github.com/repos/{owner}/{repo.lower()}", token)
            if info is not None:
                repo = repo.lower()

        if info is None:
            if args.strict:
                raise SystemExit(f"Repo not accessible: {owner}/{repo}")
            name = c.title or repo
            description = c.description or ""
            language = ""
            stars = 0
            forks = 0
            pushed = ""
        else:
            name = c.title or (info.get("name") or repo)
            description = c.description or (info.get("description") or "")
            language = info.get("language") or ""
            stars = int(info.get("stargazers_count") or 0)
            forks = int(info.get("forks_count") or 0)
            pushed = parse_date(info.get("pushed_at") or "")

        href = c.href or f"https://github.com/{owner}/{repo}"
        logo_uri = logo_to_data_uri(c.logo, root)

        svg = render_card_svg(
            width=args.width,
            height=args.height,
            name=name,
            subtitle=c.subtitle,
            description=description,
            language=language,
            stars=stars,
            forks=forks,
            pushed=pushed,
            href=href,
            logo_data_uri=logo_uri,
        )

        (out_dir / f"{slug_for(c, default_user)}.svg").write_text(svg, encoding="utf-8")

    write_embed(cards, default_user, out_dir)


if __name__ == "__main__":
    main()
