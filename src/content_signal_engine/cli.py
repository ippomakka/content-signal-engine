from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .analyse import analyse_signal
from .comments import load_comments_file
from .discover import (
    DAILY_WEB_QUERIES,
    DAILY_REDDIT_QUERIES,
    candidates_to_watch_items,
    discover_from_source_seeds,
    discover_with_ytdlp,
    instagram_reels_url,
    load_source_seeds,
    search_duckduckgo,
    search_reddit_pullpush,
)
from .models import AnalysedSignal, WatchItem
from .notion_direct import load_run, sync_generated_scripts, sync_run_to_notion
from .notion_export import export_notion_csv, write_notion_payload
from .report import write_outputs
from .schedule import cron_hint, write_runner
from .scrape import platform_from_url, probe_metadata, signal_from_metadata, transcribe
from .scripts import generate_scripts as generate_scripts_from_items, write_generated_scripts
from .storage import (
    DISCOVERY_DIR,
    RUNS_DIR,
    SOURCE_SEEDS_PATH,
    ensure_dirs,
    load_patterns,
    load_watchlist,
    save_watchlist,
    upsert_patterns,
)

app = typer.Typer(help="Local-first content intelligence for social content signals.")
console = Console()


def previously_scanned_urls() -> set[str]:
    """Return URLs that have already been analysed in prior runs."""
    urls: set[str] = set()
    for path in RUNS_DIR.glob("*.json"):
        try:
            items = load_run(path)
        except Exception:
            continue
        urls.update(item.signal.url for item in items)
    return urls


@app.command()
def init() -> None:
    """Create local data directories and starter files."""
    ensure_dirs()
    console.print("[green]Initialised data/ watchlist, report, run, media and pattern-bank storage.[/green]")


@app.command("add-url")
def add_url(
    url: Annotated[str, typer.Argument(help="Public Reel/post/video URL")],
    creator: Annotated[str | None, typer.Option(help="Creator/account label")] = None,
    lane: Annotated[str | None, typer.Option(help="Niche lane, e.g. digital minimalism")] = None,
    notes: Annotated[str | None, typer.Option(help="Why this source matters")] = None,
) -> None:
    """Add a URL to the scan watchlist."""
    items = load_watchlist()
    if any(item.url == url for item in items):
        console.print("[yellow]URL is already in the watchlist.[/yellow]")
        return
    items.append(WatchItem(url=url, creator=creator, lane=lane, notes=notes))
    save_watchlist(items)
    console.print(f"[green]Added[/green] {url}")


@app.command("discover-account")
def discover_account(
    handle_or_url: Annotated[str, typer.Argument(help="Instagram handle like @lyndonslife or a public account/reels URL")],
    max_results: Annotated[int, typer.Option(help="Maximum posts to discover")] = 12,
    add: Annotated[bool, typer.Option(help="Add discovered posts to watchlist")] = False,
    lane: Annotated[str | None, typer.Option(help="Niche lane to attach if adding")] = None,
) -> None:
    """Discover recent posts from a public account/reels page using yt-dlp flat playlist."""
    source_url = handle_or_url if handle_or_url.startswith("http") else instagram_reels_url(handle_or_url)
    console.print(f"[cyan]Discovering[/cyan] {source_url}")
    try:
        posts = discover_with_ytdlp(source_url, max_results=max_results)
    except RuntimeError as exc:
        console.print("[yellow]Could not discover posts from this public account page.[/yellow]")
        console.print("[yellow]Public account discovery is platform/extractor dependent; add specific post URLs with `cse add-url` when a site blocks listing.[/yellow]")
        console.print(str(exc).splitlines()[-1])
        raise typer.Exit(1)
    table = Table(title="Discovered posts")
    table.add_column("#")
    table.add_column("Creator")
    table.add_column("Title")
    table.add_column("URL")
    for idx, post in enumerate(posts, 1):
        table.add_row(str(idx), post.creator or "", (post.title or "")[:60], post.url)
    console.print(table)
    if add:
        items = load_watchlist()
        existing = {item.url for item in items}
        added = 0
        creator = handle_or_url.lstrip("@").split("/")[0] if not handle_or_url.startswith("http") else None
        for post in posts:
            if post.url not in existing:
                items.append(WatchItem(url=post.url, creator=post.creator or creator, lane=lane, notes="discovered from account"))
                existing.add(post.url)
                added += 1
        save_watchlist(items)
        console.print(f"[green]Added {added} new posts to watchlist.[/green]")


@app.command("discover-daily")
def discover_daily(
    add: Annotated[bool, typer.Option(help="Add addable fresh candidates to the watchlist")] = False,
    max_sources: Annotated[int | None, typer.Option(help="Limit seeded creator sources checked today")] = None,
    max_per_source: Annotated[int, typer.Option(help="Fresh posts to keep from each seeded creator source")] = 2,
    web_results: Annotated[int, typer.Option(help="Audience-pain web results to collect per query; use 0 to skip web search")] = 3,
) -> None:
    """Discover fresh daily candidates from seeded creators plus audience-pain web searches.

    This is the robust discovery layer before scanning: it rotates through seeded
    sources, skips previously scanned/watchlisted URLs, records web pain-language
    candidates, and can add fresh video/social URLs to the watchlist.
    """
    ensure_dirs()
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    seeds = load_source_seeds(SOURCE_SEEDS_PATH)
    existing = {item.url for item in load_watchlist()} | previously_scanned_urls()
    creator_candidates, errors = discover_from_source_seeds(
        seeds,
        existing_urls=set(existing),
        max_sources=max_sources,
        max_per_source=max_per_source,
    )
    web_candidates = []
    if web_results > 0:
        for subreddit, query, lane in DAILY_REDDIT_QUERIES:
            try:
                web_candidates.extend(search_reddit_pullpush(subreddit, query, lane, max_results=web_results))
            except Exception as exc:
                errors.append(f"reddit query failed: r/{subreddit} {query} — {exc}")
        # DuckDuckGo HTML search is a fallback/additional broad web source. It can
        # be sparse or bot-blocked, so failures here are non-fatal.
        for query, lane in DAILY_WEB_QUERIES:
            try:
                results = search_duckduckgo(query, max_results=web_results)
            except Exception as exc:
                errors.append(f"web query failed: {query} — {exc}")
                continue
            for result in results:
                web_candidates.append(result.__class__(**{**result.__dict__, "lane": lane}))

    all_candidates = creator_candidates + web_candidates
    report_path = DISCOVERY_DIR / f"{run_id}.json"
    report_path.write_text(json.dumps([candidate.__dict__ for candidate in all_candidates], indent=2) + "\n")

    added = 0
    if add:
        items = load_watchlist()
        watch_existing = {item.url for item in items}
        new_items = []
        for item in candidates_to_watch_items(creator_candidates):
            if item.url not in watch_existing:
                new_items.append(item)
                watch_existing.add(item.url)
        if new_items:
            save_watchlist([*items, *new_items])
            added = len(new_items)

    table = Table(title="Daily discovery candidates")
    table.add_column("#")
    table.add_column("Kind")
    table.add_column("Creator/Source")
    table.add_column("Lane")
    table.add_column("Title")
    table.add_column("URL")
    for idx, candidate in enumerate(all_candidates[:40], 1):
        kind = "scan" if candidate.addable else "pain"
        table.add_row(str(idx), kind, candidate.creator or candidate.source[:30], candidate.lane[:28], candidate.title[:55], candidate.url[:75])
    console.print(table)
    console.print(f"[green]Discovery report:[/green] {report_path}")
    if add:
        console.print(f"[green]Added {added} fresh creator/social candidates to watchlist.[/green]")
    if errors:
        console.print("[yellow]Discovery caveats:[/yellow]")
        for error in errors[:8]:
            console.print(f"- {error}")


@app.command("list")
def list_items() -> None:
    """List watchlist URLs."""
    items = load_watchlist()
    table = Table(title="Watchlist")
    table.add_column("#")
    table.add_column("Creator")
    table.add_column("Lane")
    table.add_column("URL")
    for idx, item in enumerate(items, 1):
        table.add_row(str(idx), item.creator or "", item.lane or "", item.url)
    console.print(table)


@app.command()
def scan(
    limit: Annotated[int | None, typer.Option(help="Maximum watchlist items to scan")] = None,
    platform: Annotated[str | None, typer.Option(help="Only scan a specific platform, e.g. instagram, youtube, tiktok")] = None,
    fresh: Annotated[bool, typer.Option(help="Skip URLs already analysed in previous runs; use --no-fresh to deliberately rescan")] = True,
    no_transcribe: Annotated[bool, typer.Option(help="Skip Whisper transcription and analyse metadata/caption only")] = False,
    whisper_model: Annotated[str, typer.Option(help="Whisper model to use when transcribing")] = "small.en",
    comments_file: Annotated[Path | None, typer.Option(help="Optional JSON/text comments export for audience-language extraction")] = None,
    notion_export: Annotated[bool, typer.Option(help="Write Notion-ready CSV exports after scanning")] = False,
    notion_sync: Annotated[bool, typer.Option(help="Directly sync this run to Don's Notion Daily Content Signals databases")] = False,
    script_count: Annotated[int, typer.Option(help="Number of review scripts to auto-generate after analysis; use 0 to disable")] = 3,
) -> None:
    """Scan watchlist URLs, analyse signals, and write a report."""
    ensure_dirs()
    items = load_watchlist()
    if platform:
        wanted = platform.lower()
        items = [item for item in items if platform_from_url(item.url) == wanted]
    if fresh:
        seen = previously_scanned_urls()
        items = [item for item in items if item.url not in seen]
    if limit is not None:
        items = items[:limit]
    if not items:
        if fresh:
            console.print("[yellow]No fresh watchlist URLs left. Add/discover new URLs, rotate the watchlist, or use `--no-fresh` to deliberately rescan.[/yellow]")
        else:
            console.print("[yellow]Watchlist is empty. Add URLs with `cse add-url ...`.[/yellow]")
        raise typer.Exit(1)
    manual_comments = load_comments_file(comments_file) if comments_file else {}
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    analysed: list[AnalysedSignal] = []
    for idx, item in enumerate(items, 1):
        console.print(f"[cyan]({idx}/{len(items)}) Probing[/cyan] {item.url}")
        metadata = probe_metadata(item.url)
        signal = signal_from_metadata(item.url, metadata, item)
        signal.audience_comments.extend(manual_comments.get("*", []))
        signal.audience_comments.extend(manual_comments.get(item.url, []))
        if not no_transcribe:
            console.print("  transcribing audio with Whisper...")
            signal.transcript = transcribe(item.url, f"{run_id}-{idx}", whisper_model)
        analysis = analyse_signal(signal)
        analysed.append(AnalysedSignal(signal=signal, analysis=analysis))
        console.print(f"  [green]done[/green] hook={analysis.hook_type}, Don-fit={analysis.don_fit_score}/10")
    upsert_patterns(analysed)
    json_path, md_path = write_outputs(analysed, run_id)
    console.print(f"[green]Report written:[/green] {md_path}")
    console.print(f"[green]JSON written:[/green] {json_path}")
    if notion_export:
        signal_csv, pattern_csv, summary_csv = export_notion_csv(analysed, run_id)
        payload = write_notion_payload(analysed, run_id)
        console.print(f"[green]Notion CSVs:[/green] {signal_csv}, {pattern_csv}, {summary_csv}")
        console.print(f"[green]Notion JSON payload:[/green] {payload}")
    generated_scripts = []
    if script_count > 0:
        generated_scripts = generate_scripts_from_items(analysed, top=script_count)
        scripts_md, scripts_json = write_generated_scripts(generated_scripts, run_id)
        console.print(f"[green]Generated {len(generated_scripts)} review scripts:[/green] {scripts_md}")
    if notion_sync:
        result = sync_run_to_notion(analysed, run_id)
        console.print(f"[green]Synced {len(result.daily_signal_pages)} signals to Notion.[/green]")
        if result.summary_page:
            console.print(f"[green]Summary page:[/green] {result.summary_page}")
        if generated_scripts:
            script_pages = sync_generated_scripts(generated_scripts, run_id)
            console.print(f"[green]Synced {len(script_pages)} generated scripts to Notion for review.[/green]")


@app.command("export-notion")
def export_notion(run_json: Annotated[Path, typer.Argument(help="Path to a data/runs/*.json file")]) -> None:
    """Create Notion-ready CSV files from an existing run JSON."""
    import json

    items = [AnalysedSignal.model_validate(item) for item in json.loads(run_json.read_text())]
    run_id = run_json.stem
    signal_csv, pattern_csv, summary_csv = export_notion_csv(items, run_id)
    payload = write_notion_payload(items, run_id)
    console.print(f"[green]Notion CSVs:[/green] {signal_csv}, {pattern_csv}, {summary_csv}")
    console.print(f"[green]Notion JSON payload:[/green] {payload}")


@app.command("sync-notion")
def sync_notion(run_json: Annotated[Path, typer.Argument(help="Path to a data/runs/*.json file")]) -> None:
    """Directly sync an existing run into Don's Notion Daily Content Signals databases."""
    items = load_run(run_json)
    result = sync_run_to_notion(items, run_json.stem)
    console.print(f"[green]Synced {len(result.daily_signal_pages)} Daily Signal Log rows.[/green]")
    console.print(f"[green]Synced {len(result.pattern_pages)} Pattern Bank rows.[/green]")
    if result.summary_page:
        console.print(f"[green]Summary page:[/green] {result.summary_page}")


@app.command("generate-scripts")
def generate_scripts_cmd(
    run_json: Annotated[Path, typer.Argument(help="Path to a data/runs/*.json file")],
    top: Annotated[int, typer.Option(help="Number of scripts to generate")] = 3,
    notion_sync: Annotated[bool, typer.Option(help="Also sync generated scripts to Notion Generated Scripts for review")] = False,
) -> None:
    """Generate ready-to-film Don-style scripts from a scan run."""
    items = load_run(run_json)
    scripts = generate_scripts_from_items(items, top=top)
    md_path, json_path = write_generated_scripts(scripts, run_json.stem)
    console.print(f"[green]Generated {len(scripts)} scripts:[/green] {md_path}")
    console.print(f"[green]JSON:[/green] {json_path}")
    if notion_sync:
        pages = sync_generated_scripts(scripts, run_json.stem)
        console.print(f"[green]Synced {len(pages)} generated scripts to Notion for review.[/green]")


@app.command("schedule-helper")
def schedule_helper(
    limit: Annotated[int, typer.Option(help="Limit for scheduled scans")] = 20,
    no_transcribe: Annotated[bool, typer.Option(help="Create runner that skips Whisper transcription")] = False,
) -> None:
    """Create a weekly-report shell runner and print a Hermes cron prompt suggestion."""
    project_dir = Path.cwd().resolve()
    script = write_runner(project_dir, limit=limit, no_transcribe=no_transcribe)
    console.print(f"[green]Runner written:[/green] {script}")
    console.print(cron_hint(project_dir, limit=limit, no_transcribe=no_transcribe))


@app.command("patterns")
def patterns() -> None:
    """Show the current pattern bank."""
    patterns = load_patterns()
    table = Table(title="Pattern Bank")
    table.add_column("Times")
    table.add_column("Type")
    table.add_column("Pattern")
    table.add_column("Don version")
    for pattern in sorted(patterns, key=lambda p: p.times_seen, reverse=True):
        table.add_row(str(pattern.times_seen), pattern.pattern_type, pattern.name, pattern.don_version)
    console.print(table)


if __name__ == "__main__":
    app()
