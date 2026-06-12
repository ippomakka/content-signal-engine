from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import AnalysedSignal
from .storage import DATA_DIR, ensure_dirs

SCRIPTS_DIR = DATA_DIR / "generated_scripts"

DON_LANES = ["Autopilot", "Default Life", "Presence / Reality Is Weird", "Becoming Yourself"]


@dataclass(frozen=True)
class GeneratedScript:
    title: str
    source_url: str
    inspired_by: str
    lane: str
    hook: str
    on_screen_text: str
    script: str
    caption: str
    anti_content_bro_check: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "source_url": self.source_url,
            "inspired_by": self.inspired_by,
            "lane": self.lane,
            "hook": self.hook,
            "on_screen_text": self.on_screen_text,
            "script": self.script,
            "caption": self.caption,
            "anti_content_bro_check": self.anti_content_bro_check,
        }


def choose_lane(item: AnalysedSignal) -> str:
    text = " ".join(
        part.lower()
        for part in [item.signal.title, item.signal.caption, item.signal.transcript, item.analysis.reusable_pattern]
        if part
    )
    if any(word in text for word in ["scroll", "phone", "screen", "morning", "attention", "decision", "routine"]):
        return "Autopilot"
    if any(word in text for word in ["job", "success", "status", "money", "career", "lifestyle"]):
        return "Default Life"
    if any(word in text for word in ["life", "meaning", "exist", "world", "reality", "wonder"]):
        return "Presence / Reality Is Weird"
    return "Becoming Yourself"


def title_for_lane(lane: str) -> str:
    return {
        "Autopilot": "The tiny escape route stealing your day",
        "Default Life": "Succeeding at the wrong life",
        "Presence / Reality Is Weird": "Reality feels fake until you slow down",
        "Becoming Yourself": "The fear of being honest about what you want",
    }.get(lane, "Trying to wake up in public")


def clean_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def trim_words(text: str | None, limit: int = 18) -> str:
    words = clean_text(text).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(",.;:") + "..."


def source_insight(item: AnalysedSignal) -> str:
    """Use the actual scanned signal as the seed so daily scripts do not repeat templates."""
    for candidate in [item.analysis.hook, item.signal.title, item.signal.caption]:
        cleaned = trim_words(candidate, 24)
        if cleaned:
            return cleaned
    return "a normal moment suddenly feeling stranger than it should"


def source_title(item: AnalysedSignal, lane: str) -> str:
    theme = theme_from_signal(item)
    if theme == "night_before":
        return "Your morning starts the night before"
    if theme == "micro_interactions":
        return "Your life changes in tiny moments"
    if theme == "borrowed_beliefs":
        return "Old fear with better branding"
    insight = trim_words(source_insight(item), 8).rstrip(".")
    return f"{lane}: {insight}"


def question_from_signal(item: AnalysedSignal, lane: str) -> str:
    hook = clean_text(item.analysis.hook).lower()
    if "opinion" in hook or "judge" in hook or "other people" in hook:
        return "how much of me is just borrowed from other people?"
    if "complicated" in hook or "desires" in hook or "want" in hook:
        return "why is it so hard to say what i actually want?"
    if "drink" in hook or "convincing" in hook or "no" in hook:
        return "where am i still explaining boundaries that should be obvious?"
    if "time" in hook or "routine" in hook or "desk" in hook:
        return "is this helping me live, or just helping me optimise?"
    if lane == "Default Life":
        return "what if i win the wrong game?"
    if lane == "Autopilot":
        return "what am i trying not to feel?"
    if lane == "Presence / Reality Is Weird":
        return "who is actually steering this thing?"
    return "what am i avoiding being honest about?"


def hook_from_signal(item: AnalysedSignal, lane: str) -> str:
    hook = clean_text(item.analysis.hook).lower()
    if "morning routine" in hook or "life hacking" in hook:
        return "I don’t think the problem is my morning routine. I think it’s what I let happen the night before."
    if "divorced" in hook or "positive interactions" in hook:
        return "Apparently relationships die in tiny moments. I think our lives probably do too."
    if "dating beliefs" in hook or "myth versus fact" in hook:
        return "I keep wondering how many beliefs I call standards are actually just old fear wearing a nice outfit."
    if "opinion" in hook or "other people" in hook:
        return "I keep thinking about how much of my self-image is rented from other people."
    if "complicated" in hook or "desires" in hook or "want" in hook:
        return "I don’t think I’m unclear because I have no direction. I think I’m scared of wanting the wrong thing out loud."
    if "drink" in hook or "convincing" in hook or "no" in hook:
        return "It’s weird how fast a tiny boundary can show you who actually respects your life."
    if "time" in hook or "routine" in hook or "desk" in hook:
        return "I’m starting to realise optimisation can become another way to avoid being present."
    return hook_for_lane(lane)


def theme_from_signal(item: AnalysedSignal) -> str | None:
    hook = clean_text(item.analysis.hook).lower()
    text = " ".join(clean_text(part).lower() for part in [item.signal.transcript, item.signal.caption, item.signal.title])
    if "morning routine" in hook or "night before" in text or "decision fatigue" in text:
        return "night_before"
    if "divorced" in hook or "positive interactions" in text or "negative interactions" in text:
        return "micro_interactions"
    if "dating beliefs" in hook or "myth versus fact" in hook:
        return "borrowed_beliefs"
    return None


def hook_for_lane(lane: str) -> str:
    return {
        "Autopilot": "I keep calling it a quick scroll, but sometimes it feels more like leaving the room without moving.",
        "Default Life": "The scariest thing isn’t failing. It’s succeeding at a life you secretly don’t want.",
        "Presence / Reality Is Weird": "Sometimes normal life only feels normal because we stopped paying attention.",
        "Becoming Yourself": "I used to think I needed more discipline. I think I actually needed fewer escape routes.",
    }.get(lane, "I’m trying to wake up from autopilot, and it’s weirder than I expected.")


def script_for(item: AnalysedSignal) -> GeneratedScript:
    lane = choose_lane(item)
    hook = hook_from_signal(item, lane)
    title = source_title(item, lane)
    source_line = item.analysis.reusable_pattern
    insight = source_insight(item)
    on_screen = question_from_signal(item, lane)
    platform_line = (
        "I saw an Instagram Reel today that hit because it named something specific."
        if item.signal.platform == "instagram"
        else "I saw a short today that hit because it named something specific."
    )
    theme = theme_from_signal(item)

    if theme == "night_before":
        body = f"""{hook}

Because I keep trying to fix my life at the exact moment I have the least energy to fix it.

I wake up tired and expect morning-me to be some disciplined little monk.

But morning-me is just me with worse hair and less patience.

So maybe the real move is less glamorous.

Make the decision before I’m tired.
Put the phone somewhere annoying before I want it.
Choose the first task before the day starts bargaining with me.

Not because I’m trying to become some optimised productivity robot.

Because I’m trying to stop handing the first hour of my life to whatever app screams the loudest.

That’s the uncomfortable part.

A lot of my autopilot doesn’t start in the moment I scroll.

It starts the night before, when I leave every escape route open.

So tonight I’m making tomorrow slightly harder to abandon.

Tiny, boring, probably effective.

Annoying."""
        on_screen = "your morning starts the night before"
    elif theme == "micro_interactions":
        body = f"""{hook}

Not in one dramatic movie scene.

In tiny little moments you barely count.

The eye roll.
The sharp reply.
The dismissive laugh.
The one second where someone reaches for connection and you’re half inside your phone.

And I’ve been thinking about that beyond relationships.

Because maybe a life doesn’t fall apart in one huge decision either.

Maybe it’s all the tiny interactions you have with yourself.

You say you want peace, then start the morning with panic scrolling.
You say you want freedom, then keep asking strangers online who you’re allowed to be.
You say you want a real life, then disappear into the screen every time silence shows up.

None of it feels that serious in the moment.

But it stacks.

And eventually your life starts reflecting the tiny things you kept letting slide.

That is deeply rude of reality.

But probably useful."""
        on_screen = "your life changes in tiny moments"
    elif theme == "borrowed_beliefs":
        body = f"""{hook}

I’ll call something a preference.

But if I’m honest, sometimes it’s just protection.

I’ll say “I’m just not that kind of person.”

But sometimes that means I tried something once, felt embarrassed, and built a whole identity around never risking that feeling again.

That’s what scares me about autopilot.

It doesn’t always feel like scrolling or wasting time.

Sometimes it sounds mature.
It sounds logical.
It sounds like standards.
It sounds like “that’s just who I am.”

And maybe some of it is true.

But I want to get better at asking:

Did I choose this belief consciously?

Or did I inherit it from fear and then decorate it so it looked like wisdom?

Because I don’t want a personality that is mostly old avoidance with better branding."""
        on_screen = "is this belief mine, or just old fear?"
    elif lane == "Autopilot":
        body = f"""{hook}

{platform_line}

The surface idea was basically:

{insight}

But the bit I care about is what it points to in my own day.

Yesterday I opened Instagram before I even knew what I was feeling.

Not because I had something to check.

Not because anyone messaged me.

Just pure muscle memory.

Like my brain hit the emergency exit before I had to sit with myself for two seconds.

And that’s the weird part.

We call it procrastination.
We call it being tired.
We call it needing a break.

But sometimes I think scrolling is just the socially acceptable way to disappear from your own life for a bit.

So I’m trying to stop making it this huge self-improvement project.

Before fixing my whole life, I just want to notice the first tiny moment I abandon it.

For me, it’s usually the phone.

So today I’m trying this:

When I reach for it, I pause and ask, “What am I trying not to feel?”

Annoyingly, that question works.

And I kind of hate that."""
    elif lane == "Default Life":
        body = f"""{hook}

{platform_line}

The surface idea was basically:

{insight}

And it made me think about the life I keep accidentally practising for.

Because failing would at least be honest.

You tried something.
It didn’t work.
It hurt.
But at least it was yours.

What scares me more is doing everything “right” and slowly becoming a stranger to myself.

Getting good at the routine.
Getting praised for the version of me that knows how to perform.
Staying busy enough that I never have to ask if I even wanted this.

Because I don’t think most people are lazy.

I think a lot of us are exhausted from living lives we never consciously chose.

And that’s what I’m trying to wake up from.

Not dramatically.

Just honestly.

One uncomfortable question at a time."""
    elif lane == "Presence / Reality Is Weird":
        body = f"""{hook}

{platform_line}

The surface idea was basically:

{insight}

And it did that thing good content does.

It made something normal feel suspicious again.

Like, have you ever looked around and realised how much of your day is just… assumed?

Wake up.
Check the rectangle.
Answer messages.
Be productive.
Consume something.
Feel behind.
Repeat.

And somehow that’s considered normal.

That’s the interruption I keep coming back to.

The moment where a normal habit suddenly looks strange.

Because I think waking up isn’t always some massive spiritual moment.

Sometimes it’s just standing in your kitchen, holding your phone, realising you haven’t had a real thought all morning.

And instead of judging yourself, you get curious.

Like… wait.

Who is actually steering this thing?

That question has been following me around lately."""
    else:
        body = f"""{hook}

{platform_line}

The surface idea was basically:

{insight}

But the part that stuck with me was honesty.

Because every time I try to change my life, I notice how many little doors I’ve built to avoid myself.

The phone.
The jokes.
The “I’m just tired.”
The pretending I don’t care.
The waiting until I feel ready.

And then I wonder why nothing feels like it’s moving.

And here’s the honest version.

I don’t think I’m stuck because I don’t know what to do.

I think I’m stuck because doing it would make the old version of me impossible to keep defending.

And that’s embarrassing.

But also kind of freeing.

Because maybe becoming yourself starts with admitting how much energy you spend avoiding yourself."""

    caption = caption_for(lane)
    return GeneratedScript(
        title=title,
        source_url=item.signal.url,
        inspired_by=item.analysis.reusable_pattern,
        lane=lane,
        hook=hook,
        on_screen_text=on_screen,
        script=body.strip(),
        caption=caption,
        anti_content_bro_check=[
            "No fake certainty or guru posture",
            "Starts from a lived/confessional moment",
            "Steals the structure, not the creator's wording/persona",
            "CTA stays journey-based or omitted",
        ],
    )


def caption_for(lane: str) -> str:
    keywords = "autopilot, doomscrolling, attention, digital minimalism, self awareness, purpose, meaning, authentic life"
    if lane == "Autopilot":
        return (
            "I keep calling scrolling a break, but I don’t always feel rested after.\n\n"
            "Sometimes the phone isn’t the problem. It’s the escape route.\n\n"
            "Follow along if you’re trying to wake up too.\n\n"
            f"Keywords: {keywords}"
        )
    if lane == "Default Life":
        return (
            "I don’t want a life that only looks good from the outside.\n\n"
            "I want one that actually feels like mine.\n\n"
            "Follow along if you’ve felt that too.\n\n"
            f"Keywords: default life, purpose, meaning, self awareness, authentic life, personal growth"
        )
    if lane == "Presence / Reality Is Weird":
        return (
            "Modern life gets really strange when you stop treating it as normal.\n\n"
            "Maybe waking up starts with noticing what you’ve been accepting.\n\n"
            f"Keywords: consciousness, presence, autopilot, modern life, self awareness, meaning"
        )
    return (
        "Maybe becoming yourself starts with noticing all the tiny ways you avoid yourself.\n\n"
        "That’s the bit I’m trying to get honest about.\n\n"
        f"Keywords: authenticity, purpose, self awareness, personal growth, meaning, identity"
    )


def generate_scripts(items: list[AnalysedSignal], top: int = 3) -> list[GeneratedScript]:
    ranked = sorted(items, key=lambda item: (item.analysis.don_fit_score, item.analysis.outlier_score), reverse=True)
    scripts: list[GeneratedScript] = []
    used_lanes: set[str] = set()
    for item in ranked:
        generated = script_for(item)
        if generated.lane in used_lanes and len(scripts) < min(top, len(DON_LANES)):
            # Encourage variety in the first few scripts where possible.
            continue
        scripts.append(generated)
        used_lanes.add(generated.lane)
        if len(scripts) >= top:
            return scripts
    for item in ranked:
        if len(scripts) >= top:
            break
        generated = script_for(item)
        is_duplicate = any(
            existing.source_url == generated.source_url
            or existing.hook == generated.hook
            or existing.title == generated.title
            for existing in scripts
        )
        if not is_duplicate:
            scripts.append(generated)
    return scripts[:top]


def render_scripts_markdown(scripts: list[GeneratedScript], run_id: str) -> str:
    lines = [f"# Generated Don-Style Scripts — {run_id}", ""]
    lines.append("> These are adapted from source mechanics, not copied from source wording/persona.")
    lines.append("")
    for idx, script in enumerate(scripts, 1):
        lines.extend([
            f"## {idx}. {script.title}",
            "",
            f"- Lane: {script.lane}",
            f"- Source: {script.source_url}",
            f"- Inspired by: {script.inspired_by}",
            "",
            "### On-screen text",
            "",
            script.on_screen_text,
            "",
            "### Script",
            "",
            script.script,
            "",
            "### Caption",
            "",
            script.caption,
            "",
            "### Anti-content-bro check",
            "",
        ])
        lines.extend([f"- {item}" for item in script.anti_content_bro_check])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_generated_scripts(scripts: list[GeneratedScript], run_id: str) -> tuple[Path, Path]:
    ensure_dirs()
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = SCRIPTS_DIR / f"{run_id}-scripts.md"
    json_path = SCRIPTS_DIR / f"{run_id}-scripts.json"
    md_path.write_text(render_scripts_markdown(scripts, run_id))
    json_path.write_text(json.dumps([script.as_dict() for script in scripts], indent=2) + "\n")
    return md_path, json_path
