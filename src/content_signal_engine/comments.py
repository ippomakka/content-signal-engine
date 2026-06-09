from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

LOW_VALUE = {
    "nice", "good", "great", "love", "amazing", "wow", "yes", "no", "lol", "bro", "true",
    "facts", "first", "thanks", "thank you", "fire", "🔥", "❤️", "👏",
}


def comments_from_metadata(metadata: dict[str, Any]) -> list[str]:
    """Extract public comments if the platform extractor exposes them.

    Most Instagram public pages only expose comment counts, not comment text. This function is
    deliberately conservative: if comment text is absent, it returns an empty list instead of
    pretending we have audience language.
    """
    raw = metadata.get("comments") or metadata.get("__comments") or []
    comments: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = item.get("text") or item.get("comment") or item.get("content") or ""
            else:
                text = ""
            text = clean_comment(text)
            if text:
                comments.append(text)
    return comments


def load_comments_file(path: str | Path) -> dict[str, list[str]]:
    """Load optional manual/exported comments.

    Accepted shapes:
    - JSON list of strings: applies to all scanned URLs under key "*"
    - JSON object mapping URL to list[str]
    - Plain text file: one comment per line, applies to all scanned URLs
    """
    p = Path(path)
    text = p.read_text().strip()
    if not text:
        return {}
    if p.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, list):
            return {"*": [clean_comment(str(x)) for x in data if clean_comment(str(x))]}
        if isinstance(data, dict):
            out: dict[str, list[str]] = {}
            for key, value in data.items():
                if isinstance(value, list):
                    out[str(key)] = [clean_comment(str(x)) for x in value if clean_comment(str(x))]
            return out
    return {"*": [clean_comment(line) for line in text.splitlines() if clean_comment(line)]}


def clean_comment(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:500]


def extract_audience_phrases(comments: list[str], fallback_text: str = "", limit: int = 8) -> list[str]:
    """Find strong audience language from comments, then fall back to self-recognition lines."""
    candidates: list[str] = []
    for comment in comments:
        c = clean_comment(comment)
        lower = c.lower()
        if len(c) < 12 or lower in LOW_VALUE:
            continue
        if any(marker in lower for marker in ["this is me", "literally me", "felt this", "needed this", "i feel", "i'm", "im ", "i am", "why am i", "same"]):
            candidates.append(c)
    if len(candidates) < limit and fallback_text:
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", fallback_text).strip())
        for sentence in sentences:
            lower = sentence.lower()
            if 20 <= len(sentence) <= 180 and any(w in lower for w in ["i ", "we ", "you ", "scared", "lost", "stuck", "phone", "life", "feel"]):
                candidates.append(sentence)
    # Deduplicate while preserving order and prefer emotionally specific phrases.
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []
    emotion_terms = ["feel", "scared", "lost", "stuck", "empty", "alone", "phone", "life", "silence", "anxious", "needed"]
    for phrase in candidates:
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        score = sum(1 for term in emotion_terms if term in key) + min(len(phrase) // 60, 2)
        scored.append((score, phrase))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [phrase for _, phrase in scored[:limit]]


def comment_summary(comments: list[str]) -> str:
    if not comments:
        return "No public comment text available; only comment counts may be public."
    words = Counter()
    for comment in comments:
        for word in re.findall(r"[a-zA-Z']{4,}", comment.lower()):
            if word not in LOW_VALUE:
                words[word] += 1
    common = ", ".join(word for word, _ in words.most_common(8))
    return f"{len(comments)} public comments available. Repeated language: {common or 'not enough repeated language'}."
