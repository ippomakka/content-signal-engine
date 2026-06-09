from content_signal_engine.models import AnalysedSignal, PostSignal
from content_signal_engine.analyse import analyse_signal
from content_signal_engine.report import render_markdown


def test_report_contains_public_data_note_and_transcript():
    signal = PostSignal(
        url="https://example.com/reel/1",
        platform="instagram",
        creator="demo",
        transcript="I realised I was opening my phone before I knew what I felt.",
    )
    item = AnalysedSignal(signal=signal, analysis=analyse_signal(signal))
    report = render_markdown([item], "test-run")
    assert "Public-data note" in report
    assert "Don-style content directions" in report
    assert "Transcript" in report
