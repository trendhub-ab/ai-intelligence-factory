import types

import article_revalidation as ar


def test_stale_ready_rehydrates_legacy_hn_discovery_url_before_generation():
    p = types.SimpleNamespace()
    p.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
    p._resolve_producthunt_official_url = lambda url: ""
    p.resolve_recovery_primary_url = lambda repo: "https://netflixtechblog.com/genrec-primary"
    item = {
        "revalidation_stale_ready": True,
        "repo": {
            "source": "HackerNews",
            "url": "https://news.ycombinator.com/item?id=123",
            "primaryUrl": "https://news.ycombinator.com/item?id=123",
            "sourceDetails": {"regen_note": "legacy"},
        },
    }
    repo = ar.rehydrate_recovery_repo(p, item)
    assert repo["url"] == "https://news.ycombinator.com/item?id=123"
    assert repo["primaryUrl"] == "https://netflixtechblog.com/genrec-primary"
    assert repo["sourceDetails"]["external_url"] == "https://netflixtechblog.com/genrec-primary"


def test_rehydration_fails_closed_when_no_durable_primary_can_be_resolved():
    p = types.SimpleNamespace(resolve_recovery_primary_url=lambda repo: "")
    item = {"revalidation_stale_ready": True, "repo": {"source": "HackerNews", "url": "https://news.ycombinator.com/item?id=123", "primaryUrl": "https://news.ycombinator.com/item?id=123"}}
    assert ar.rehydrate_recovery_repo(p, item) is None


def test_non_stale_recovery_does_not_rewrite_source_identity():
    p = types.SimpleNamespace(resolve_recovery_primary_url=lambda repo: "https://example.com/unused")
    repo = {"source": "GitHub", "url": "https://github.com/acme/tool", "primaryUrl": "https://github.com/acme/tool"}
    assert ar.rehydrate_recovery_repo(p, {"repo": repo}) == repo
