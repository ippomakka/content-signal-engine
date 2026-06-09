from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .comments import comments_from_metadata
from .models import PostSignal, PublicMetrics, WatchItem
from .storage import MEDIA_DIR, ensure_dirs


def platform_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "instagram" in host:
        return "instagram"
    if "tiktok" in host:
        return "tiktok"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    return host or "unknown"


def _run_json(args: list[str], timeout: int = 180) -> dict:
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return json.loads(proc.stdout)


def probe_metadata(url: str) -> dict:
    return _run_json(["uvx", "--from", "yt-dlp", "yt-dlp", "--dump-single-json", "--skip-download", url])


def _metric_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def signal_from_metadata(url: str, metadata: dict, item: WatchItem | None = None) -> PostSignal:
    creator = item.creator if item and item.creator else metadata.get("uploader") or metadata.get("channel")
    caption = metadata.get("description") or metadata.get("fulltitle") or metadata.get("title")
    return PostSignal(
        url=url,
        platform=platform_from_url(url),
        creator=creator,
        title=metadata.get("title") or metadata.get("fulltitle"),
        caption=caption,
        duration=metadata.get("duration"),
        upload_date=metadata.get("upload_date"),
        metrics=PublicMetrics(
            views=_metric_int(metadata.get("view_count")),
            likes=_metric_int(metadata.get("like_count")),
            comments=_metric_int(metadata.get("comment_count")),
            reposts=_metric_int(metadata.get("repost_count")),
        ),
        audience_comments=comments_from_metadata(metadata),
        raw_metadata={
            "id": metadata.get("id"),
            "extractor": metadata.get("extractor"),
            "webpage_url": metadata.get("webpage_url"),
            "availability": metadata.get("availability"),
        },
    )


def download_audio(url: str, run_id: str) -> Path:
    ensure_dirs()
    out_template = str(MEDIA_DIR / f"{run_id}.%(ext)s")
    proc = subprocess.run(
        ["uvx", "--from", "yt-dlp", "yt-dlp", "-f", "bv*+ba/b", "-o", out_template, url],
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    candidates = sorted(MEDIA_DIR.glob(f"{run_id}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("yt-dlp finished but no media file was created")
    media = candidates[0]
    wav = MEDIA_DIR / f"{run_id}.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to extract audio")
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    media.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return wav


def transcribe(url: str, run_id: str, model: str = "small.en") -> str:
    wav = download_audio(url, run_id)
    proc = subprocess.run(
        [
            "uvx",
            "--from",
            "openai-whisper",
            "whisper",
            str(wav),
            "--model",
            model,
            "--output_dir",
            str(MEDIA_DIR),
            "--output_format",
            "txt",
            "--fp16",
            "False",
        ],
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    wav.unlink(missing_ok=True)
    txt = MEDIA_DIR / f"{run_id}.txt"
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    transcript = txt.read_text().strip() if txt.exists() else ""
    txt.unlink(missing_ok=True)
    for leftover in MEDIA_DIR.glob(f"{run_id}.*"):
        leftover.unlink(missing_ok=True)
    return re.sub(r"\n{3,}", "\n\n", transcript).strip()
