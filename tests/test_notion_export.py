from content_signal_engine.analyse import analyse_signal
from content_signal_engine.models import AnalysedSignal, PostSignal
from content_signal_engine.notion_export import export_notion_csv


def test_notion_export_writes_expected_csvs(tmp_path, monkeypatch):
    import content_signal_engine.notion_export as notion_export

    monkeypatch.setattr(notion_export, "NOTION_DIR", tmp_path / "notion_exports")
    signal = PostSignal(
        url="https://example.com/reel/1",
        platform="instagram",
        creator="demo",
        transcript="I caught myself opening my phone before I knew what I felt.",
        audience_comments=["this is literally me, I feel stuck"],
    )
    item = AnalysedSignal(signal=signal, analysis=analyse_signal(signal))
    paths = export_notion_csv([item], "test-run")
    for path in paths:
        assert path.exists()
    assert "Daily Signal Log" not in paths[0].read_text()
    assert "this is literally me" in paths[0].read_text()
