from __future__ import annotations

from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .analyse import analyse_signal
from .models import AnalysedSignal, WatchItem
from .report import write_outputs
from .scrape import probe_metadata, signal_from_metadata, transcribe
from .storage import ensure_dirs, load_patterns, load_watchlist, save_watchlist, upsert_patterns

app = typer.Typer(help="Local-first content intelligence for social content signals.")
console = Console()


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
    no_transcribe: Annotated[bool, typer.Option(help="Skip Whisper transcription and analyse metadata/caption only")] = False,
    whisper_model: Annotated[str, typer.Option(help="Whisper model to use when transcribing")] = "small.en",
) -> None:
    """Scan watchlist URLs, analyse signals, and write a report."""
    ensure_dirs()
    items = load_watchlist()
    if limit is not None:
        items = items[:limit]
    if not items:
        console.print("[yellow]Watchlist is empty. Add URLs with `cse add-url ...`.[/yellow]")
        raise typer.Exit(1)
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    analysed: list[AnalysedSignal] = []
    for idx, item in enumerate(items, 1):
        console.print(f"[cyan]({idx}/{len(items)}) Probing[/cyan] {item.url}")
        metadata = probe_metadata(item.url)
        signal = signal_from_metadata(item.url, metadata, item)
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
