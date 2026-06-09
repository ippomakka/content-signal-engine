from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from .models import AnalysedSignal
from .report import render_markdown
from .scripts import GeneratedScript

NOTION_VERSION = "2025-09-03"

# Don's existing Daily Content Signals databases under A New Reality.
DEFAULT_DAILY_SIGNAL_DB = "4c19d2da-5bfb-4888-ab96-d43f6016d451"
DEFAULT_PATTERN_BANK_DB = "b879df0a-4d24-46c3-82b8-27ac5444e882"
DEFAULT_DAILY_SUMMARY_DB = "9242d78a-4cca-410a-aa3a-c43db5a41dae"
DEFAULT_GENERATED_SCRIPTS_DB = "e8841671-8865-4748-9a9c-73a8024b9c92"


@dataclass(frozen=True)
class NotionSyncResult:
    daily_signal_pages: list[str]
    pattern_pages: list[str]
    summary_page: str | None
    script_pages: list[str] | None = None


def _token() -> str:
    token = os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_API_TOKEN")
    if not token:
        raise RuntimeError("NOTION_API_KEY or NOTION_API_TOKEN is required for direct Notion sync")
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def notion_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        data=body,
        headers=_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8")
        raise RuntimeError(f"Notion API {method} {path} failed: {exc.code} {message}") from exc


def title(text: str) -> dict[str, Any]:
    return {"title": [{"text": {"content": text[:2000]}}]}


def rich(text: str) -> dict[str, Any]:
    return {"rich_text": [{"text": {"content": (text or "")[:2000]}}]}


def select(name: str | None) -> dict[str, Any]:
    return {"select": {"name": (name or "Unknown")[:100]}}


def multi_select(names: list[str]) -> dict[str, Any]:
    return {"multi_select": [{"name": name[:100]} for name in names if name]}


def date_prop(value: str | None = None) -> dict[str, Any]:
    if value and len(value) == 8 and value.isdigit():
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return {"date": {"start": value or datetime.utcnow().date().isoformat()}}


def paragraph(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def heading(text: str, level: int = 2) -> dict[str, Any]:
    typ = f"heading_{level}"
    return {"object": "block", "type": typ, typ: {"rich_text": [{"text": {"content": text[:2000]}}]}}


def bullet(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": text[:2000]}}]}}


T = TypeVar("T")


def chunks(items: list[T], size: int = 90) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def create_page(database_id: str, properties: dict[str, Any], children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"parent": {"database_id": database_id}, "properties": properties}
    if children:
        payload["children"] = children[:90]
    page = notion_request("POST", "pages", payload)
    remaining = children[90:] if children else []
    for batch in chunks(remaining):
        notion_request("PATCH", f"blocks/{page['id']}/children", {"children": batch})
    return page


def performance_text(item: AnalysedSignal) -> str:
    s = item.signal
    metrics: list[str] = []
    if s.metrics.views is not None:
        metrics.append(f"views: {s.metrics.views:,}")
    if s.metrics.likes is not None:
        metrics.append(f"likes: {s.metrics.likes:,}")
    if s.metrics.comments is not None:
        metrics.append(f"comments: {s.metrics.comments:,}")
    return ", ".join(metrics) if metrics else "public metrics unavailable"


def signal_children(item: AnalysedSignal) -> list[dict[str, Any]]:
    s, a = item.signal, item.analysis
    blocks = [
        heading("Why it worked", 2),
        *[bullet(reason) for reason in a.why_it_worked],
        heading("Don adaptation", 2),
        paragraph(a.don_adaptation),
        heading("Audience language", 2),
    ]
    if a.audience_phrases:
        blocks.extend(bullet(phrase) for phrase in a.audience_phrases)
    else:
        blocks.append(paragraph("Public comment text unavailable; using visible metrics/transcript only."))
    blocks.extend([
        heading("Idea seeds", 2),
        *[bullet(seed) for seed in a.idea_seeds],
    ])
    if s.transcript:
        blocks.extend([heading("Transcript", 2), paragraph(s.transcript[:8000])])
    return blocks


def sync_daily_signal(item: AnalysedSignal, database_id: str) -> str:
    s, a = item.signal, item.analysis
    props = {
        "Name": title(a.hook[:90] or s.title or "Untitled signal"),
        "Date": date_prop(s.upload_date),
        "Platform": select(s.platform.title() if s.platform else "Unknown"),
        "Creator / Source": rich(s.creator or ""),
        "Link": {"url": s.url},
        "Niche Lane": multi_select(["Creator Tooling"] if "viral" in (s.transcript or s.caption or "").lower() else []),
        "Performance": rich(performance_text(item)),
        "Hook": rich(a.hook),
        "Format": select(a.format_type[:100]),
        "Emotional Driver": select(a.emotional_driver.title()),
        "Why It Worked": rich("\n".join(a.why_it_worked)),
        "Don Adaptation": rich(a.don_adaptation),
        "Status": select("Decoded"),
    }
    return create_page(database_id, props, signal_children(item))["url"]


def sync_pattern(item: AnalysedSignal, database_id: str) -> str:
    a = item.analysis
    props = {
        "Name": title(a.reusable_pattern[:90]),
        "Pattern Type": select("Hook"),
        "Description": rich(a.reusable_pattern),
        "Example Found": rich(item.signal.url),
        "Don Version": rich(a.don_adaptation),
        "Use Next?": {"checkbox": a.don_fit_score >= 6},
    }
    return create_page(database_id, props)["url"]


def sync_summary(items: list[AnalysedSignal], run_id: str, database_id: str) -> str | None:
    if not items:
        return None
    strongest = max(items, key=lambda item: (item.analysis.don_fit_score, item.analysis.outlier_score))
    report = render_markdown(items, run_id)
    props = {
        "Name": title(f"Content Signal Engine — {run_id}"),
        "Date": date_prop(),
        "Main Signal": rich(strongest.analysis.reusable_pattern),
        "Strongest Audience Phrase": rich(strongest.analysis.audience_phrases[0] if strongest.analysis.audience_phrases else "No public comment text available"),
        "Best Content Direction": rich(strongest.analysis.idea_seeds[0] if strongest.analysis.idea_seeds else ""),
        "Caveat / Source Notes": rich("Public data only. Saves, shares, reach, retention, and true watch time are not inferred."),
        "Status": select("Logged"),
    }
    children = [heading("Full report", 2)]
    # Keep Notion legible: chunk the markdown into paragraph-sized sections rather than line-per-block.
    for section in report.split("\n\n")[:80]:
        section = section.strip()
        if not section:
            continue
        if section.startswith("# "):
            children.append(heading(section.lstrip("# ").strip(), 1))
        elif section.startswith("## "):
            children.append(heading(section.lstrip("# ").strip(), 2))
        elif section.startswith("- "):
            for line in section.splitlines():
                children.append(bullet(line[2:] if line.startswith("- ") else line))
        else:
            children.append(paragraph(section))
    return create_page(database_id, props, children)["url"]


def sync_generated_script(script: GeneratedScript, run_id: str, database_id: str, priority: str = "Medium") -> str:
    props = {
        "Name": title(script.title),
        "Status": select("Review"),
        "Date": date_prop(),
        "Lane": select(script.lane),
        "Source URL": {"url": script.source_url},
        "Hook": rich(script.hook),
        "On-screen Text": rich(script.on_screen_text),
        "Caption": rich(script.caption),
        "Run ID": rich(run_id),
        "Priority": select(priority),
    }
    children = [
        heading("On-screen text", 2),
        paragraph(script.on_screen_text),
        heading("Script", 2),
        paragraph(script.script),
        heading("Caption", 2),
        paragraph(script.caption),
        heading("Source pattern", 2),
        paragraph(f"Inspired by: {script.inspired_by}"),
        paragraph(f"Source: {script.source_url}"),
        heading("Anti-content-bro check", 2),
        *[bullet(item) for item in script.anti_content_bro_check],
    ]
    return create_page(database_id, props, children)["url"]


def sync_generated_scripts(
    scripts: list[GeneratedScript],
    run_id: str,
    database_id: str = DEFAULT_GENERATED_SCRIPTS_DB,
) -> list[str]:
    pages: list[str] = []
    for idx, script in enumerate(scripts):
        priority = "High" if idx == 0 else "Medium"
        pages.append(sync_generated_script(script, run_id, database_id, priority=priority))
    return pages


def sync_run_to_notion(
    items: list[AnalysedSignal],
    run_id: str,
    daily_signal_db: str = DEFAULT_DAILY_SIGNAL_DB,
    pattern_bank_db: str = DEFAULT_PATTERN_BANK_DB,
    daily_summary_db: str = DEFAULT_DAILY_SUMMARY_DB,
) -> NotionSyncResult:
    signal_pages = [sync_daily_signal(item, daily_signal_db) for item in items]
    pattern_pages = [sync_pattern(item, pattern_bank_db) for item in items]
    summary_page = sync_summary(items, run_id, daily_summary_db)
    return NotionSyncResult(signal_pages, pattern_pages, summary_page)


def load_run(path: Path) -> list[AnalysedSignal]:
    return [AnalysedSignal.model_validate(item) for item in json.loads(path.read_text())]
