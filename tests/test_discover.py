from content_signal_engine.discover import instagram_reels_url


def test_instagram_reels_url_from_handle():
    assert instagram_reels_url("@lyndonslife") == "https://www.instagram.com/lyndonslife/reels/"
