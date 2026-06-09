from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import AnalysedSignal
from .storage import REPORTS_DIR, RUNS_DIR, ensure_dirs


def render_markdown(items: list[AnalysedSignal], run_id: str) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Content Signal Report — {run_id}",
        "",
        f"Generated: {now}",
        "",
        "> Public-data note: this report only uses public metadata/transcripts. Saves, shares, reach, retention, and true watch time are not inferred or fabricated.",
        "",
    ]
    ranked = sorted(items, key=lambda item: (item.analysis.don_fit_score, item.analysis.outlier_score), reverse=True)
    if ranked:
        top = ranked[0]
        lines += [
            "## Today's strongest signal",
            "",
            f"**Main signal:** {top.analysis.reusable_pattern}",
            "",
            f"**Don translation:** {top.analysis.don_adaptation}",
            "",
            "## Best Don-style content directions",
            "",
        ]
        seen: set[str] = set()
        count = 1
        for item in ranked:
            for seed in item.analysis.idea_seeds:
                if seed not in seen:
                    lines.append(f"{count}. {seed}")
                    seen.add(seed)
                    count += 1
                if count > 10:
                    break
            if count > 10:
                break
        lines.append("")
    lines += ["## Analysed posts", ""]
    for idx, item in enumerate(ranked, 1):
        s = item.signal
        a = item.analysis
        metrics = []
        if s.metrics.views is not None:
            metrics.append(f"views: {s.metrics.views:,}")
        if s.metrics.likes is not None:
            metrics.append(f"likes: {s.metrics.likes:,}")
        if s.metrics.comments is not None:
            metrics.append(f"comments: {s.metrics.comments:,}")
        metric_text = ", ".join(metrics) if metrics else "public metrics unavailable"
        lines += [
            f"### {idx}. {s.creator or s.platform or 'Unknown creator'}",
            "",
            f"- URL: {s.url}",
            f"- Platform: {s.platform}",
            f"- Public metrics: {metric_text}",
            f"- Outlier score: {a.outlier_score}",
            f"- Don-fit score: {a.don_fit_score}/10",
            f"- Hook: {a.hook}",
            f"- Hook type: {a.hook_type}",
            f"- Emotional driver: {a.emotional_driver}",
            f"- Format: {a.format_type}",
            "",
            "**Why it worked**",
            "",
        ]
        lines.extend([f"- {reason}" for reason in a.why_it_worked])
        lines += [
            "",
            f"**Reusable pattern:** {a.reusable_pattern}",
            "",
            f"**Don adaptation:** {a.don_adaptation}",
            "",
        ]
        if a.anti_pattern_flags:
            lines += ["**Watch-outs**", ""]
            lines.extend([f"- {flag}" for flag in a.anti_pattern_flags])
            lines.append("")
        if s.transcript:
            transcript = s.transcript.strip()
            if len(transcript) > 1800:
                transcript = transcript[:1800].rstrip() + "..."
            lines += ["<details><summary>Transcript</summary>", "", transcript, "", "</details>", ""]
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(items: list[AnalysedSignal], run_id: str) -> tuple[Path, Path]:
    ensure_dirs()
    json_path = RUNS_DIR / f"{run_id}.json"
    md_path = REPORTS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps([item.model_dump(mode="json") for item in items], indent=2) + "\n")
    md_path.write_text(render_markdown(items, run_id))
    return json_path, md_path
