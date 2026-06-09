from content_signal_engine.comments import extract_audience_phrases, load_comments_file, comments_from_metadata


def test_extract_audience_phrases_prefers_self_recognition_comments():
    comments = [
        "nice",
        "this is literally me, I open my phone before I know what I feel",
        "I needed this because I feel so stuck lately",
    ]
    phrases = extract_audience_phrases(comments)
    assert phrases[0].startswith("this is literally me")
    assert len(phrases) == 2


def test_comments_from_metadata_is_conservative():
    metadata = {"comment_count": 100}
    assert comments_from_metadata(metadata) == []


def test_load_comments_file_plain_text(tmp_path):
    p = tmp_path / "comments.txt"
    p.write_text("this is me\n\nneeded this today\n")
    assert load_comments_file(p) == {"*": ["this is me", "needed this today"]}
