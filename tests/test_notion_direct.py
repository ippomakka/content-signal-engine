from content_signal_engine import notion_direct


def test_existing_page_url_builds_exact_url_filter(monkeypatch):
    calls = []

    def fake_request(method, path, payload=None):
        calls.append((method, path, payload))
        return {"results": [{"url": "https://app.notion.com/p/existing"}]}

    monkeypatch.setattr(notion_direct, "notion_request", fake_request)

    url = notion_direct.existing_page_url("ds-id", "Link", "url", "https://example.com/post")

    assert url == "https://app.notion.com/p/existing"
    assert calls == [
        (
            "POST",
            "data_sources/ds-id/query",
            {
                "filter": {"property": "Link", "url": {"equals": "https://example.com/post"}},
                "page_size": 1,
            },
        )
    ]


def test_existing_page_url_returns_none_when_no_match(monkeypatch):
    monkeypatch.setattr(notion_direct, "notion_request", lambda *args, **kwargs: {"results": []})

    assert notion_direct.existing_page_url("ds-id", "Source URL", "url", "https://example.com/post") is None


def test_sync_generated_script_skips_duplicate_source_url(monkeypatch):
    created = []
    script = notion_direct.GeneratedScript(
        title="Demo",
        lane="Autopilot",
        source_url="https://example.com/post",
        hook="hook",
        on_screen_text="text",
        script="script",
        caption="caption",
        inspired_by="pattern",
        anti_content_bro_check=["check"],
    )

    monkeypatch.setattr(notion_direct, "existing_page_url", lambda *args, **kwargs: "https://app.notion.com/p/existing")
    monkeypatch.setattr(notion_direct, "create_page", lambda *args, **kwargs: created.append(args) or {"url": "created"})

    url = notion_direct.sync_generated_script(script, "run-id", notion_direct.DEFAULT_GENERATED_SCRIPTS_DB)

    assert url == "https://app.notion.com/p/existing"
    assert created == []
