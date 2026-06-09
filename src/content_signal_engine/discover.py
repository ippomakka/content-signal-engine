from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass(frozen=True)
class DiscoveredPost:
    url: str
    title: str | None = None
    creator: str | None = None


def instagram_reels_url(handle: str) -> str:
    clean = handle.strip().lstrip("@").strip("/")
    return f"https://www.instagram.com/{clean}/reels/"


def discover_with_ytdlp(source_url: str, max_results: int = 12) -> list[DiscoveredPost]:
    """Discover recent posts from a public account/reels page using yt-dlp flat playlist.

    Public platform access is fragile; callers should surface failures honestly.
    """
    proc = subprocess.run(
        ["uvx", "--from", "yt-dlp", "yt-dlp", "--flat-playlist", "--dump-single-json", source_url],
        text=True,
        capture_output=True,
        timeout=240,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    data = json.loads(proc.stdout)
    entries = data.get("entries") or []
    discovered: list[DiscoveredPost] = []
    for entry in entries[:max_results]:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url") or entry.get("webpage_url") or entry.get("original_url")
        if not url:
            entry_id = entry.get("id")
            if entry_id:
                url = urljoin(source_url, str(entry_id))
        if url and not str(url).startswith("http"):
            url = urljoin(source_url, str(url))
        if url:
            discovered.append(DiscoveredPost(url=str(url), title=entry.get("title"), creator=entry.get("uploader") or data.get("uploader")))
    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[DiscoveredPost] = []
    for item in discovered:
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)
    return unique
