from content_signal_engine.analyse import analyse_signal, classify_hook, don_fit
from content_signal_engine.models import PostSignal, PublicMetrics


def test_classify_proof_demo_hook():
    assert classify_hook("I just built this Claude skill that predicts what to post") == "proof/demo claim"


def test_don_fit_penalises_content_bro_language():
    score, flags = don_fit("viral funnel hack scale dominate 10x")
    assert score <= 4
    assert "leans content-bro / growth-hack" in flags


def test_analyse_signal_generates_don_adaptation():
    signal = PostSignal(
        url="https://example.com/reel/1",
        platform="instagram",
        creator="demo",
        duration=81,
        metrics=PublicMetrics(views=200000, likes=10000, comments=200),
        transcript=(
            "I just built this system that finds top performing posts. "
            "Here is exactly how it works. Phase one, scrape creators. "
            "Phase two, analyse transcripts. Phase three, write a report."
        ),
    )
    analysis = analyse_signal(signal)
    assert analysis.hook_type == "proof/demo claim"
    assert analysis.outlier_score > 1
    assert "building in public" in analysis.don_adaptation
    assert analysis.idea_seeds
