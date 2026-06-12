from __future__ import annotations

import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

from .models import WatchItem
from .scrape import platform_from_url


@dataclass(frozen=True)
class DiscoveredPost:
    url: str
    title: str | None = None
    creator: str | None = None


@dataclass(frozen=True)
class SourceSeed:
    creator: str
    platform: str
    url: str
    lane: str
    why: str | None = None


@dataclass(frozen=True)
class DiscoveryCandidate:
    url: str
    title: str
    creator: str | None
    lane: str
    source: str
    reason: str
    platform: str = "unknown"
    addable: bool = True


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


def load_source_seeds(path) -> list[SourceSeed]:
    if not path.exists():
        return []
    return [SourceSeed(**item) for item in json.loads(path.read_text())]


DAILY_WEB_QUERIES: list[tuple[str, str]] = [
    ('site:reddit.com/r/nosurf "phone" "autopilot" OR "scrolling"', "Autopilot / attention"),
    ('site:reddit.com/r/findapath "25" "stuck" "life"', "Purpose / stuckness"),
    ('site:reddit.com/r/GenZ "AI" "future" "job"', "AI + being human"),
    ('site:reddit.com/r/Existentialism "wasting my life" OR "wasting time"', "Existential fear / meaning"),
    ('site:reddit.com/r/digitalminimalism "brain" "phone"', "Digital minimalism"),
]

DAILY_REDDIT_QUERIES: list[tuple[str, str, str]] = [
    ("nosurf", "phone scrolling autopilot", "Autopilot / attention"),
    ("findapath", "25 stuck life", "Purpose / stuckness"),
    ("GenZ", "AI future job", "AI + being human"),
    ("Existentialism", "wasting my life", "Existential fear / meaning"),
    ("digitalminimalism", "brain phone", "Digital minimalism"),
]


def _ddg_result_url(raw_href: str) -> str:
    raw_href = html.unescape(raw_href)
    parsed = urllib.parse.urlparse(raw_href)
    qs = urllib.parse.parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        return qs["uddg"][0]
    return raw_href


def search_duckduckgo(query: str, max_results: int = 5) -> list[DiscoveryCandidate]:
    """Return lightweight public web-search candidates via DuckDuckGo HTML.

    This is intentionally dependency-free and best-effort. It is for audience-pain
    discovery and candidate sourcing, not private platform analytics.
    """
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
    matches = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.S)
    candidates: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    for href, title_html in matches:
        result_url = _ddg_result_url(href)
        if result_url in seen:
            continue
        seen.add(result_url)
        title = re.sub(r"<.*?>", "", title_html)
        title = html.unescape(re.sub(r"\s+", " ", title)).strip()
        candidates.append(
            DiscoveryCandidate(
                url=result_url,
                title=title or result_url,
                creator=None,
                lane="Audience pain / web search",
                source=f"web query: {query}",
                reason="Public search result for raw audience language; inspect before turning into a signal.",
                platform=platform_from_url(result_url),
                addable=platform_from_url(result_url) in {"youtube", "instagram", "tiktok"},
            )
        )
        if len(candidates) >= max_results:
            break
    return candidates


def search_reddit_pullpush(subreddit: str, query: str, lane: str, max_results: int = 5) -> list[DiscoveryCandidate]:
    """Search public Reddit submissions through PullPush for raw audience language."""
    params = urllib.parse.urlencode({"q": query, "subreddit": subreddit, "size": max_results})
    url = f"https://api.pullpush.io/reddit/search/submission/?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    candidates: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    for post in payload.get("data", []):
        permalink = post.get("permalink")
        if not permalink:
            continue
        post_url = "https://www.reddit.com" + permalink if permalink.startswith("/") else permalink
        if post_url in seen:
            continue
        seen.add(post_url)
        title = html.unescape(post.get("title") or post_url).strip()
        selftext = re.sub(r"\s+", " ", html.unescape(post.get("selftext") or "")).strip()
        reason = "Raw audience-language Reddit thread"
        if selftext:
            reason += f": {selftext[:180]}"
        candidates.append(
            DiscoveryCandidate(
                url=post_url,
                title=title,
                creator=f"r/{subreddit}",
                lane=lane,
                source=f"pullpush reddit search: r/{subreddit} {query}",
                reason=reason,
                platform="reddit",
                addable=False,
            )
        )
        if len(candidates) >= max_results:
            break
    return candidates


def discover_from_source_seeds(
    seeds: list[SourceSeed],
    existing_urls: set[str],
    max_sources: int | None = None,
    max_per_source: int = 3,
) -> tuple[list[DiscoveryCandidate], list[str]]:
    candidates: list[DiscoveryCandidate] = []
    errors: list[str] = []
    selected = seeds[:max_sources] if max_sources else seeds
    for seed in selected:
        try:
            posts = discover_with_ytdlp(seed.url, max_results=max_per_source * 3)
        except RuntimeError as exc:
            errors.append(f"{seed.creator}: {str(exc).splitlines()[-1]}")
            continue
        added_for_source = 0
        for post in posts:
            if post.url in existing_urls:
                continue
            candidates.append(
                DiscoveryCandidate(
                    url=post.url,
                    title=post.title or post.url,
                    creator=post.creator or seed.creator,
                    lane=seed.lane,
                    source=seed.url,
                    reason=seed.why or "Fresh post from seeded creator source.",
                    platform=platform_from_url(post.url),
                    addable=True,
                )
            )
            existing_urls.add(post.url)
            added_for_source += 1
            if added_for_source >= max_per_source:
                break
    return candidates, errors


def candidates_to_watch_items(candidates: list[DiscoveryCandidate]) -> list[WatchItem]:
    return [
        WatchItem(url=item.url, creator=item.creator, lane=item.lane, notes=f"daily discovery: {item.reason}")
        for item in candidates
        if item.addable
    ]
