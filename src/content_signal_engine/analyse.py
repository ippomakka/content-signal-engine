from __future__ import annotations

import re

from .comments import extract_audience_phrases
from .models import PostSignal, SignalAnalysis

DON_KEYWORDS = {
    "autopilot",
    "doomscroll",
    "phone",
    "scroll",
    "attention",
    "conscious",
    "consciousness",
    "purpose",
    "meaning",
    "freedom",
    "default",
    "life",
    "identity",
    "authentic",
    "ai",
    "human",
    "lost",
    "stuck",
    "wake",
    "alive",
}

CONTENT_BRO_WORDS = {
    "viral",
    "scale",
    "funnel",
    "hack",
    "crush",
    "dominate",
    "unstoppable",
    "millionaire",
    "grind",
    "alpha",
    "10x",
}

EMOTION_WORDS = {
    "fear": {"scared", "afraid", "fear", "anxious", "panic", "terrified"},
    "relief": {"relief", "finally", "free", "peace", "calm", "breathe"},
    "identity": {"i am", "person", "identity", "become", "version", "self"},
    "rebellion": {"default", "escape", "quit", "refuse", "orders", "system"},
    "curiosity": {"why", "secret", "exactly", "how", "what if", "realised"},
    "shame": {"embarrassed", "ashamed", "hate", "guilty", "hide"},
    "hope": {"possible", "hope", "build", "change", "start", "wake"},
}


def first_sentences(text: str, count: int = 2) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return " ".join(parts[:count]).strip() or clean[:180]


def classify_hook(hook: str) -> str:
    h = hook.lower()
    if "i just" in h or "i tried" in h or "i built" in h:
        return "proof/demo claim"
    if any(word in h for word in ["i used to", "i realised", "i realized", "i don't think", "i didn’t", "i didn't"]):
        return "confessional realisation"
    if "?" in h or h.startswith("why") or h.startswith("what"):
        return "question"
    if any(word in h for word in ["but", "instead", "actually", "not"]):
        return "contradiction"
    if any(word in h for word in ["how to", "exactly", "here's how", "here is how"]):
        return "promise/framework"
    return "statement"


def emotional_driver(text: str) -> str:
    lower = text.lower()
    scores = {name: sum(1 for word in words if word in lower) for name, words in EMOTION_WORDS.items()}
    best = max(scores, key=lambda name: scores[name])
    return best if scores[best] else "curiosity"


def format_type(signal: PostSignal, text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["phase one", "phase two", "step one", "here is exactly how"]):
        return "framework/demo breakdown"
    if any(term in lower for term in ["i was", "yesterday", "last week", "when i"]):
        return "personal story"
    if signal.platform == "instagram" and signal.duration and signal.duration < 20:
        return "short punchy reel"
    if signal.duration and signal.duration > 60:
        return "explainer reel"
    return "talking-head insight"


def outlier_score(signal: PostSignal) -> float:
    m = signal.metrics
    score = 1.0
    if m.views:
        score += min(m.views / 100_000, 8)
    if m.likes:
        score += min(m.likes / 10_000, 5)
    if m.comments:
        score += min(m.comments / 500, 4)
    if m.views and m.comments:
        score += min((m.comments / max(m.views, 1)) * 1000, 3)
    return round(score, 2)


def don_fit(text: str) -> tuple[int, list[str]]:
    lower = text.lower()
    pos = sum(1 for word in DON_KEYWORDS if word in lower)
    neg = sum(1 for word in CONTENT_BRO_WORDS if word in lower)
    score = max(1, min(10, 4 + pos - neg))
    flags: list[str] = []
    if neg >= 2:
        flags.append("leans content-bro / growth-hack")
    if "comment" in lower and "below" in lower:
        flags.append("engagement-bait CTA")
    if len(text.split()) > 260:
        flags.append("long for one-point short-form")
    if score <= 4:
        flags.append("weak fit with Don's waking-up/autopilot world")
    return score, flags


def why_it_worked(hook_type: str, driver: str, fmt: str, signal: PostSignal) -> list[str]:
    reasons = [f"The opening uses a {hook_type} hook, so the viewer understands the payoff quickly."]
    reasons.append(f"The emotional driver is {driver}, which gives the post a clear feeling instead of just information.")
    reasons.append(f"The format reads as {fmt}, making the idea easy to package and repeat.")
    if signal.metrics.views or signal.metrics.likes or signal.metrics.comments:
        reasons.append("It has visible public performance signals, so it is worth studying without pretending to know private saves/shares.")
    return reasons


def reusable_pattern(hook_type: str, driver: str, fmt: str) -> str:
    if hook_type == "proof/demo claim":
        return "Proof-first demo: bold result → quick credibility → show the system → invite the viewer into the mechanism."
    if hook_type == "confessional realisation":
        return "Confession to meaning: private uncomfortable moment → honest realisation → broader truth → soft challenge."
    if hook_type == "contradiction":
        return "Contradiction hook: expected belief → uncomfortable opposite → lived example → new frame."
    return f"{hook_type.title()} + {driver}: open with the tension, make it concrete, then translate it into a repeatable {fmt}."


def don_adaptation_for(pattern: str, driver: str) -> str:
    if "Proof-first demo" in pattern:
        return "Turn the demo into a transparent 'building in public' post: show the system finding signals, then ask what it says about our attention instead of flexing virality."
    if "Confession" in pattern:
        return "Start with a small embarrassing autopilot moment, then zoom out into what it says about modern attention and choosing a life that feels like yours."
    return f"Translate the {driver} into Don's world: less guru certainty, more honest best-friend realisation about waking up from autopilot."


def idea_seeds(driver: str, fmt: str) -> list[str]:
    return [
        "I don't think we're addicted to our phones. I think we're scared of the silence after we put them down.",
        "I caught myself opening Instagram before I even knew what I was feeling. That scared me more than the screen time number.",
        "The weirdest part about trying to wake up is realising how much of your day was never really yours.",
        f"A {fmt} about the moment you realise the problem isn't discipline, it's all the tiny escape routes you built.",
    ]


def analyse_signal(signal: PostSignal) -> SignalAnalysis:
    text = "\n".join(part for part in [signal.transcript, signal.caption, signal.title] if part)
    hook = first_sentences(text)
    hook_type = classify_hook(hook)
    driver = emotional_driver(text)
    fmt = format_type(signal, text)
    fit, flags = don_fit(text)
    audience_phrases = extract_audience_phrases(signal.audience_comments, text)
    pattern = reusable_pattern(hook_type, driver, fmt)
    return SignalAnalysis(
        hook=hook,
        hook_type=hook_type,
        emotional_driver=driver,
        format_type=fmt,
        why_it_worked=why_it_worked(hook_type, driver, fmt, signal),
        audience_phrases=audience_phrases,
        don_fit_score=fit,
        outlier_score=outlier_score(signal),
        anti_pattern_flags=flags,
        reusable_pattern=pattern,
        don_adaptation=don_adaptation_for(pattern, driver),
        idea_seeds=idea_seeds(driver, fmt),
    )
