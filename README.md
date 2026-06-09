# Content Signal Engine

Content Signal Engine is a local-first content intelligence CLI for finding what is resonating in a niche, decoding the reusable mechanics, and translating them into Don-style content ideas without copying anyone's voice.

## MVP features

- Watchlist-driven scans from Reel/post URLs
- Public account/reels-page discovery via `yt-dlp --flat-playlist` where the platform extractor supports listing (verified with YouTube Shorts; Instagram account listing is currently extractor-fragile, so specific Reel URLs remain the reliable Instagram path)
- `yt-dlp` metadata probing and media download
- Whisper transcription via `uvx --from openai-whisper whisper`
- Optional manual/exported comments file for audience-language extraction
- Heuristic content analysis: hook type, emotional driver, format, Don-fit score, anti-pattern flags
- Outlier scoring from public metrics when available
- Markdown + JSON reports
- Notion-ready CSV exports for Daily Signal Log, Pattern Bank, and Daily Research Summaries
- Pattern bank persistence
- Weekly report runner helper

## Requirements

- Python 3.11+
- `uv` available on PATH
- `ffmpeg` available on PATH
- Network access to public social URLs

No Instagram login is required for public URLs, but public availability can vary.

## Quick start

```bash
uv run cse --help
uv run cse init
uv run cse discover-account @somecreator --max-results 12 --add --lane "digital minimalism"
uv run cse add-url "https://www.instagram.com/reel/.../" --creator "creator_name"
uv run cse scan --limit 5 --notion-export
uv run cse scan --limit 5 --notion-sync
```

Direct sync uses Don's existing `Daily Content Signals` Notion databases under `A New Reality`:

- Daily Signal Log
- Pattern Bank
- Daily Research Summaries

You can also sync an existing run:

```bash
uv run cse sync-notion data/runs/<run-id>.json
```

Optional audience-language input when comments are exported manually:

```bash
uv run cse scan --comments-file comments.txt --notion-export
```

Create a weekly runner script:

```bash
uv run cse schedule-helper --limit 20
```

Outputs are written to `data/reports/` and structured data to `data/runs/`.

## Important limits

The system only uses public data. Instagram does not reliably expose saves, shares, reach, retention, or true watch time publicly. Those fields are never fabricated.
