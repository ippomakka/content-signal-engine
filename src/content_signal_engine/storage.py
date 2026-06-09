from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import AnalysedSignal, Pattern, WatchItem

DATA_DIR = Path("data")
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
PATTERN_BANK_PATH = DATA_DIR / "pattern_bank.json"
RUNS_DIR = DATA_DIR / "runs"
REPORTS_DIR = DATA_DIR / "reports"
MEDIA_DIR = DATA_DIR / "media"


def ensure_dirs() -> None:
    for path in [DATA_DIR, RUNS_DIR, REPORTS_DIR, MEDIA_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_PATH.exists():
        WATCHLIST_PATH.write_text("[]\n")
    if not PATTERN_BANK_PATH.exists():
        PATTERN_BANK_PATH.write_text("[]\n")


def load_watchlist() -> list[WatchItem]:
    ensure_dirs()
    return [WatchItem.model_validate(item) for item in json.loads(WATCHLIST_PATH.read_text())]


def save_watchlist(items: Iterable[WatchItem]) -> None:
    ensure_dirs()
    WATCHLIST_PATH.write_text(json.dumps([item.model_dump(mode="json") for item in items], indent=2) + "\n")


def load_patterns() -> list[Pattern]:
    ensure_dirs()
    return [Pattern.model_validate(item) for item in json.loads(PATTERN_BANK_PATH.read_text())]


def save_patterns(patterns: Iterable[Pattern]) -> None:
    ensure_dirs()
    PATTERN_BANK_PATH.write_text(json.dumps([p.model_dump(mode="json") for p in patterns], indent=2) + "\n")


def upsert_patterns(analysed: Iterable[AnalysedSignal]) -> list[Pattern]:
    patterns = load_patterns()
    by_name = {p.name.lower(): p for p in patterns}
    for item in analysed:
        name = item.analysis.reusable_pattern[:80].strip() or "Unnamed pattern"
        key = name.lower()
        if key in by_name:
            by_name[key].times_seen += 1
        else:
            pattern = Pattern(
                name=name,
                pattern_type=item.analysis.hook_type,
                description=item.analysis.reusable_pattern,
                example_url=item.signal.url,
                don_version=item.analysis.don_adaptation,
            )
            patterns.append(pattern)
            by_name[key] = pattern
    save_patterns(patterns)
    return patterns
