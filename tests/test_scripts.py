from content_signal_engine.analyse import analyse_signal
from content_signal_engine.models import AnalysedSignal, PostSignal, PublicMetrics
from content_signal_engine.scripts import generate_scripts, render_scripts_markdown


def test_generate_scripts_outputs_don_style_script():
    signal = PostSignal(
        url="https://example.com/short",
        platform="youtube",
        creator="demo",
        title="Morning routine and scrolling",
        transcript="When you wake up without a plan, you lose an hour to scrolling.",
        metrics=PublicMetrics(views=1000),
    )
    item = AnalysedSignal(signal=signal, analysis=analyse_signal(signal))
    scripts = generate_scripts([item], top=1)
    assert len(scripts) == 1
    assert scripts[0].lane == "Autopilot"
    assert "morning starts the night before" in scripts[0].on_screen_text
    assert "follow" in scripts[0].caption.lower()


def test_render_scripts_markdown_has_sections():
    signal = PostSignal(url="https://example.com", transcript="I opened my phone before thinking.")
    item = AnalysedSignal(signal=signal, analysis=analyse_signal(signal))
    md = render_scripts_markdown(generate_scripts([item], top=1), "run")
    assert "On-screen text" in md
    assert "Anti-content-bro check" in md


def test_generate_scripts_are_source_specific_not_reused_titles():
    first = PostSignal(
        url="https://www.instagram.com/reel/one/",
        platform="instagram",
        creator="creator one",
        transcript="People outsource their identity to other people's opinions and then wonder why they feel lost.",
    )
    second = PostSignal(
        url="https://www.instagram.com/reel/two/",
        platform="instagram",
        creator="creator two",
        transcript="A tiny boundary tells you who respects your life and who just wants access to it.",
    )
    scripts = generate_scripts(
        [
            AnalysedSignal(signal=first, analysis=analyse_signal(first)),
            AnalysedSignal(signal=second, analysis=analyse_signal(second)),
        ],
        top=2,
    )
    assert len({script.title for script in scripts}) == 2
    assert all(script.title not in {"The tiny escape route stealing your day", "Succeeding at the wrong life"} for script in scripts)
    assert all(script.source_url.startswith("https://www.instagram.com/reel/") for script in scripts)
