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
    assert "What am I trying not to feel" in scripts[0].script
    assert "follow" in scripts[0].caption.lower()


def test_render_scripts_markdown_has_sections():
    signal = PostSignal(url="https://example.com", transcript="I opened my phone before thinking.")
    item = AnalysedSignal(signal=signal, analysis=analyse_signal(signal))
    md = render_scripts_markdown(generate_scripts([item], top=1), "run")
    assert "On-screen text" in md
    assert "Anti-content-bro check" in md
