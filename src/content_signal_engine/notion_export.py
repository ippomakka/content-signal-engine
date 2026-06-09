from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import AnalysedSignal
from .storage import DATA_DIR, ensure_dirs, load_patterns

NOTION_DIR = DATA_DIR / "notion_exports"


def export_notion_csv(items: list[AnalysedSignal], run_id: str) -> tuple[Path, Path, Path]:
    """Export Notion-ready CSVs for Daily Signal Log, Pattern Bank, and Daily Summary.

    This avoids requiring Notion credentials in the MVP while preserving clean database rows.
    """
    ensure_dirs()
    NOTION_DIR.mkdir(parents=True, exist_ok=True)
    signal_path = NOTION_DIR / f"{run_id}-daily-signal-log.csv"
    pattern_path = NOTION_DIR / f"{run_id}-pattern-bank.csv"
    summary_path = NOTION_DIR / f"{run_id}-daily-research-summary.csv"

    with signal_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Name", "Date", "Platform", "Creator / Source", "Link", "Niche Lane", "Performance",
            "Hook", "Format", "Emotional Driver", "Why It Worked", "Don Adaptation", "Audience Phrases", "Status",
        ])
        writer.writeheader()
        for item in items:
            s, a = item.signal, item.analysis
            metrics = []
            if s.metrics.views is not None: metrics.append(f"views: {s.metrics.views}")
            if s.metrics.likes is not None: metrics.append(f"likes: {s.metrics.likes}")
            if s.metrics.comments is not None: metrics.append(f"comments: {s.metrics.comments}")
            writer.writerow({
                "Name": a.hook[:90],
                "Date": s.upload_date or "",
                "Platform": s.platform,
                "Creator / Source": s.creator or "",
                "Link": s.url,
                "Niche Lane": "",
                "Performance": ", ".join(metrics) if metrics else "public metrics unavailable",
                "Hook": a.hook,
                "Format": a.format_type,
                "Emotional Driver": a.emotional_driver,
                "Why It Worked": "\n".join(a.why_it_worked),
                "Don Adaptation": a.don_adaptation,
                "Audience Phrases": "\n".join(a.audience_phrases),
                "Status": "Decoded",
            })

    with pattern_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Name", "Pattern Type", "Description", "Example Found", "Don Version", "Use Next?", "Times Seen"])
        writer.writeheader()
        for pattern in load_patterns():
            writer.writerow({
                "Name": pattern.name,
                "Pattern Type": pattern.pattern_type,
                "Description": pattern.description,
                "Example Found": pattern.example_url,
                "Don Version": pattern.don_version,
                "Use Next?": "Yes" if pattern.times_seen > 1 else "Maybe",
                "Times Seen": pattern.times_seen,
            })

    strongest = max(items, key=lambda item: (item.analysis.don_fit_score, item.analysis.outlier_score)) if items else None
    with summary_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Name", "Date", "Main Signal", "Strongest Audience Phrase", "Best Content Direction", "Caveat / Source Notes", "Status"])
        writer.writeheader()
        writer.writerow({
            "Name": f"Research Summary {run_id}",
            "Date": run_id,
            "Main Signal": strongest.analysis.reusable_pattern if strongest else "",
            "Strongest Audience Phrase": (strongest.analysis.audience_phrases[0] if strongest and strongest.analysis.audience_phrases else "No public comment text available"),
            "Best Content Direction": (strongest.analysis.idea_seeds[0] if strongest and strongest.analysis.idea_seeds else ""),
            "Caveat / Source Notes": "Public data only. Saves, shares, reach, retention, and true watch time are not inferred.",
            "Status": "Ready to Review",
        })
    return signal_path, pattern_path, summary_path


def write_notion_payload(items: list[AnalysedSignal], run_id: str) -> Path:
    ensure_dirs(); NOTION_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTION_DIR / f"{run_id}-notion-payload.json"
    path.write_text(json.dumps([item.model_dump(mode="json") for item in items], indent=2) + "\n")
    return path
