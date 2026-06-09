#!/usr/bin/env bash
set -euo pipefail
cd /Users/ippo/projects/content-signal-engine
uv run cse scan --limit 3 --no-transcribe
latest=$(ls -t data/reports/*.md | head -1)
printf 'Content Signal Engine weekly report generated:
%s

' "$latest"
cat "$latest"
