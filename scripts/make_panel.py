#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

USER = "Tapawingo"
OUT = "assets/panel.svg"
MAX_REPOS = 6

def gh_get(url: str, token: str):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def esc(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))

def main() -> None:
    token = os.getenv("GITHUB_TOKEN", "")
    repos = gh_get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed", token)

    repos = [r for r in repos if not r.get("fork") and not r.get("archived")]
    top = repos[:MAX_REPOS]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"STATUS  //  {now}")
    if top:
        latest = top[0]
        pushed = (latest.get("pushed_at") or "")[:10]
        lines.append(f"latest push: {latest['name']} ({pushed})")
        lines.append("")
        lines.append("recently active:")
        for r in top:
            pushed = (r.get("pushed_at") or "")[:10]
            lang = r.get("language") or ""
            # fixed-ish spacing for mono font
            lines.append(f" - {r['name']:<22} {pushed}   {lang}")
    else:
        lines.append("no public repos found.")

    width, height = 1200, 320
    x, y = 72, 104
    line_h = 22

    text_elems = []
    for i, text in enumerate(lines):
        fill = "#FFFFFF" if i in (0, 1) else "#D0D0D0"
        if text.strip() == "":
            y += line_h // 2
            continue
        text_elems.append(
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="18">{esc(text)}</text>'
        )
        y += line_h

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#050505"/>
      <stop offset="1" stop-color="#0B0B0B"/>
    </linearGradient>

    <pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse">
      <rect width="6" height="6" fill="transparent"/>
      <rect y="0" width="6" height="1" fill="#FFFFFF" opacity="0.05"/>
    </pattern>

    <pattern id="dither" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="transparent"/>
      <rect x="1" y="1" width="1" height="1" fill="#fff" opacity="0.18"/>
      <rect x="5" y="2" width="1" height="1" fill="#fff" opacity="0.18"/>
      <rect x="3" y="4" width="1" height="1" fill="#fff" opacity="0.18"/>
      <rect x="7" y="6" width="1" height="1" fill="#fff" opacity="0.18"/>
      <rect x="2" y="7" width="1" height="1" fill="#fff" opacity="0.18"/>
    </pattern>
  </defs>

  <rect width="{width}" height="{height}" rx="22" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" rx="22" fill="url(#scan)" opacity="0.65"/>

  <!-- dither “glow blobs” -->
  <circle cx="1040" cy="70" r="170" fill="url(#dither)" opacity="0.95"/>
  <circle cx="210" cy="260" r="220" fill="url(#dither)" opacity="0.85"/>

  <rect x="44" y="38" width="{width-88}" height="{height-76}" rx="18"
        fill="rgba(0,0,0,0.35)" stroke="rgba(255,255,255,0.18)"/>

  <text x="{x}" y="74"
        fill="#EDEDED" font-size="16"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
    tapawingo@status:~$ cat panel.txt
  </text>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
    {''.join(text_elems)}
  </g>

  <!-- dither underline -->
  <rect x="{x}" y="{height-48}" width="520" height="10" fill="url(#dither)" opacity="0.9"/>
</svg>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
