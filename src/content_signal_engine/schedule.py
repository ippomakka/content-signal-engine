from __future__ import annotations

from pathlib import Path


def write_runner(project_dir: Path, limit: int = 20, no_transcribe: bool = False) -> Path:
    script = project_dir / "scripts" / "run_weekly_report.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    flag = " --no-transcribe" if no_transcribe else ""
    script.write_text(f"""#!/usr/bin/env bash
set -euo pipefail
cd {project_dir}
uv run cse scan --limit {limit}{flag}
latest=$(ls -t data/reports/*.md | head -1)
printf 'Content Signal Engine weekly report generated:\n%s\n\n' "$latest"
cat "$latest"
""")
    script.chmod(0o755)
    return script


def cron_hint(project_dir: Path, limit: int = 20, no_transcribe: bool = False) -> str:
    runner = write_runner(project_dir, limit=limit, no_transcribe=no_transcribe)
    return (
        "Run this weekly with cron/Hermes. Shell runner created at:\n"
        f"{runner}\n\n"
        "Hermes cron prompt suggestion:\n"
        f"Every Monday morning, run `{runner}` and deliver the resulting Content Signal Engine report back to Discord. "
        "Do not fabricate metrics; include public-data caveats."
    )
