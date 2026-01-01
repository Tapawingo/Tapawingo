#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

USER = "Tapawingo"
OUT = "assets/panel.svg"
MAX_REPOS = 6

def gh_get(url: str, token: str) -> dict | list:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))

def main() -> None:
    token = os.getenv("GITHUB_TOKEN", "")
    repos = gh_get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed", token)

    repos = [r for r in repos if not r.get("fork") and not r.get("archived")]
    top = repos[:MAX_REPOS]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[tuple[str, str]] = []
    lines.append((f"STATUS PANEL  //  {now}", "#A78BFA"))

    if top:
        latest = top[0]
        pushed = (latest.get("pushed_at") or "")[:10]
        lines.append((f"Latest push: {latest['name']}  ({pushed})", "#E5E7EB"))
        lines.append(("Active repos:", "#9CA3AF"))

        for r in top:
            pushed = (r.get("pushed_at") or "")[:10]
            lang = r.get("language") or ""
            lines.append((f" - {r['name']:<22} {pushed}   {lang}", "#9CA3AF"))
    else:
        lines.append(("No public repos found.", "#E5E7EB"))

    width, height = 1200, 320
    x = 56
    y = 92
    line_h = 22

    text_elems = []
    for text, color in lines:
        text_elems.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-size="18">{esc(text)}</text>'
        )
        y += line_h

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#070A12"/>
      <stop offset="1" stop-color="#0B1020"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#7C3AED"/>
      <stop offset="1" stop-color="#22D3EE"/>
    </linearGradient>
    <pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse">
      <path d="M0 0H6" stroke="white" stroke-opacity="0.05"/>
    </pattern>
  </defs>

  <rect width="{width}" height="{height}" rx="22" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" rx="22" fill="url(#scan)" opacity="0.45"/>
  <circle cx="1060" cy="60" r="170" fill="url(#accent)" opacity="0.12"/>

  <text x="{x}" y="56"
        fill="#B8C0FF" font-size="16"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
    tapawingo@status:~$ cat panel.txt
  </text>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
    {''.join(text_elems)}
  </g>
</svg>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
