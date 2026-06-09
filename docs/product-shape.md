# Product shape

## What this MVP is

A practical local CLI that takes known public social URLs and turns them into a structured content intelligence report.

It is intentionally not a fake "viral predictor." The first version focuses on decoding reusable content mechanics and translating them into Don's voice.

## Pipeline

1. Watchlist URLs live in `data/watchlist.json`.
2. `yt-dlp` probes public metadata.
3. Whisper transcribes video audio unless `--no-transcribe` is passed.
4. Heuristic analysis extracts:
   - hook
   - hook type
   - emotional driver
   - format type
   - outlier score
   - Don-fit score
   - anti-pattern flags
   - reusable pattern
   - Don adaptation
   - idea seeds
5. Markdown and JSON reports are written.
6. Reusable patterns are upserted into `data/pattern_bank.json`.

## Improvements planned after MVP

- Account-level scraping / recent-post discovery
- Comment-language extraction
- Notion sync for Daily Signal Log + Pattern Bank
- Scheduled cron reports
- HTML dashboard
- Creator baseline scoring for true account-relative outliers
