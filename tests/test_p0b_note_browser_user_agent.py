from __future__ import annotations

import pytest

import note_draft_automation as note


def test_standard_chrome_user_agent_preserves_engine_version_without_headless_marker():
    user_agent = note._standard_chrome_user_agent("153.0.8010.12")
    assert "HeadlessChrome" not in user_agent
    assert "Chrome/153.0.8010.12" in user_agent
    assert user_agent.startswith("Mozilla/5.0 (X11; Linux x86_64)")


def test_browser_draft_context_uses_standard_chrome_user_agent(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakePage:
        def set_default_timeout(self, _timeout):
            return None

        def goto(self, *_args, **_kwargs):
            raise RuntimeError("stop-after-context")

        def screenshot(self, **_kwargs):
            return None

    class FakeContext:
        def new_page(self):
            return FakePage()

        def close(self):
            return None

    class FakeBrowser:
        version = "153.0.8010.12"

        def new_context(self, **kwargs):
            captured.update(kwargs)
            return FakeContext()

        def close(self):
            return None

    class FakeChromium:
        def launch(self, **_kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *_args):
            return False

    import playwright.sync_api

    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: FakePlaywrightManager())

    with pytest.raises(RuntimeError, match="stop-after-context"):
        note._create_browser_draft(
            "Title",
            "Body",
            tmp_path / "eyecatch.png",
            tmp_path / "storage.json",
        )

    assert captured["user_agent"] == note._standard_chrome_user_agent("153.0.8010.12")
    assert "HeadlessChrome" not in str(captured["user_agent"])
