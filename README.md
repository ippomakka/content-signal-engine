# Content Signal Engine

Content Signal Engine is a local-first content intelligence CLI for finding what is resonating in a niche, decoding the reusable mechanics, and translating them into Don-style content ideas without copying anyone's voice.

## MVP features

- Watchlist-driven scans from Reel/post URLs
- `yt-dlp` metadata probing and media download
- Whisper transcription via `uvx --from openai-whisper whisper`
- Heuristic content analysis: hook type, emotional driver, format, Don-fit score, anti-pattern flags
- Outlier scoring from public metrics when available
- Markdown + JSON reports
- Pattern bank persistence

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
uv run cse add-url "https://www.instagram.com/reel/.../" --creator "creator_name"
uv run cse scan --limit 5
```

Outputs are written to `data/reports/` and structured data to `data/runs/`.

## Important limits

The system only uses public data. Instagram does not reliably expose saves, shares, reach, retention, or true watch time publicly. Those fields are never fabricated.
