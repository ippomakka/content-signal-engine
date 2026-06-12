from pathlib import Path
from types import SimpleNamespace

from content_signal_engine.discover import (
    DiscoveryCandidate,
    SourceSeed,
    candidates_to_watch_items,
    discover_from_source_seeds,
    instagram_reels_url,
    load_source_seeds,
    search_duckduckgo,
    search_reddit_pullpush,
)


def test_instagram_reels_url_from_handle():
    assert instagram_reels_url("@lyndonslife") == "https://www.instagram.com/lyndonslife/reels/"


def test_load_source_seeds(tmp_path):
    path = tmp_path / "source_seeds.json"
    path.write_text('[{"creator":"Demo","platform":"youtube","url":"https://youtube.com/@demo/shorts","lane":"attention","why":"fit"}]')

    seeds = load_source_seeds(path)

    assert seeds == [SourceSeed(creator="Demo", platform="youtube", url="https://youtube.com/@demo/shorts", lane="attention", why="fit")]


def test_discover_from_source_seeds_skips_existing(monkeypatch):
    from content_signal_engine import discover

    monkeypatch.setattr(
        discover,
        "discover_with_ytdlp",
        lambda url, max_results: [
            discover.DiscoveredPost(url="https://www.youtube.com/shorts/old", title="Old", creator="Demo"),
            discover.DiscoveredPost(url="https://www.youtube.com/shorts/new", title="New", creator="Demo"),
        ],
    )
    seeds = [SourceSeed(creator="Demo", platform="youtube", url="https://youtube.com/@demo/shorts", lane="attention", why="fit")]

    candidates, errors = discover_from_source_seeds(seeds, existing_urls={"https://www.youtube.com/shorts/old"}, max_per_source=2)

    assert errors == []
    assert [candidate.url for candidate in candidates] == ["https://www.youtube.com/shorts/new"]
    assert candidates[0].lane == "attention"


def test_candidates_to_watch_items_only_addable():
    candidates = [
        DiscoveryCandidate(url="https://www.youtube.com/shorts/1", title="Video", creator="Demo", lane="attention", source="seed", reason="fresh", addable=True),
        DiscoveryCandidate(url="https://reddit.com/r/nosurf/1", title="Pain", creator=None, lane="pain", source="search", reason="language", addable=False),
    ]

    items = candidates_to_watch_items(candidates)

    assert len(items) == 1
    assert items[0].url == "https://www.youtube.com/shorts/1"
    assert items[0].notes == "daily discovery: fresh"


def test_search_duckduckgo_parses_result_redirect(monkeypatch):
    html = '''
    <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reddit.com%2Fr%2Fnosurf%2Fcomments%2Fabc%2Fdemo%2F">I feel like my brain is on autopilot</a>
    '''

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return html.encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    results = search_duckduckgo('site:reddit.com/r/nosurf "autopilot"', max_results=1)

    assert len(results) == 1
    assert results[0].url == "https://www.reddit.com/r/nosurf/comments/abc/demo/"
    assert results[0].addable is False
    assert "autopilot" in results[0].title


def test_search_reddit_pullpush_parses_submission(monkeypatch):
    payload = {
        "data": [
            {
                "permalink": "/r/nosurf/comments/abc/demo/",
                "title": "I don't know how to relax without a screen",
                "selftext": "Sometimes I scroll because silence feels weird.",
            }
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            import json
            return json.dumps(payload).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    results = search_reddit_pullpush("nosurf", "phone scrolling", "Autopilot", max_results=1)

    assert results[0].url == "https://www.reddit.com/r/nosurf/comments/abc/demo/"
    assert results[0].creator == "r/nosurf"
    assert results[0].lane == "Autopilot"
    assert results[0].addable is False
    assert "silence feels weird" in results[0].reason
