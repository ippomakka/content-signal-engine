from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class WatchItem(BaseModel):
    url: str
    creator: str | None = None
    lane: str | None = None
    notes: str | None = None
    added_at: datetime = Field(default_factory=datetime.utcnow)


class PublicMetrics(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    reposts: int | None = None


class PostSignal(BaseModel):
    url: str
    platform: str = "unknown"
    creator: str | None = None
    title: str | None = None
    caption: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    metrics: PublicMetrics = Field(default_factory=PublicMetrics)
    transcript: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class SignalAnalysis(BaseModel):
    hook: str
    hook_type: str
    emotional_driver: str
    format_type: str
    why_it_worked: list[str]
    don_fit_score: int
    outlier_score: float
    anti_pattern_flags: list[str]
    reusable_pattern: str
    don_adaptation: str
    idea_seeds: list[str]


class AnalysedSignal(BaseModel):
    signal: PostSignal
    analysis: SignalAnalysis


class Pattern(BaseModel):
    name: str
    pattern_type: str
    description: str
    example_url: str
    don_version: str
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    times_seen: int = 1
