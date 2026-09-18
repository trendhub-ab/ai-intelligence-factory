from __future__ import annotations

import requests

import article_revalidation
import pipeline


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _ready_page_payload() -> dict:
    return {
        "properties": {
            pipeline.PROP_ARTICLE_STATUS: {"select": {"name": pipeline.ARTICLE_STATUS_READY}},
            pipeline.PROP_CONTENT_STATUS: {"select": {"name": pipeline.CONTENT_STATUS_DEEP_DIVE}},
        }
    }


def _install_single_ready_candidate(monkeypatch, page_id: str) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_regen_test_items",
        lambda limit, source: [
            {"notion_page_id": page_id, "repo": {"nameWithOwner": f"fixture/{page_id}"}}
        ],
    )
    monkeypatch.setattr(pipeline, "_notion_headers", lambda: {"Authorization": "test"})


def _select_stale_ready_candidate(page_id: str):
    return article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        include_quality_failed=False,
        include_stale_ready=True,
        prefer_stale_ready=True,
    )


def test_stale_ready_http_failure_is_not_treated_as_missing_manuscript(monkeypatch):
    page_id = "ready-http-503"
    _install_single_ready_candidate(monkeypatch, page_id)

    def fake_get(url, headers=None, timeout=None):
        if f"/v1/pages/{page_id}" in url:
            return _Response(200, _ready_page_payload())
        if f"/v1/blocks/{page_id}/children" in url:
            return _Response(503, {"object": "error"}, text="service unavailable")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(pipeline.requests, "get", fake_get)

    assert _select_stale_ready_candidate(page_id) == []


def test_stale_ready_transport_exception_is_not_treated_as_missing_manuscript(monkeypatch):
    page_id = "ready-transport-error"
    _install_single_ready_candidate(monkeypatch, page_id)

    def fake_get(url, headers=None, timeout=None):
        if f"/v1/pages/{page_id}" in url:
            return _Response(200, _ready_page_payload())
        if f"/v1/blocks/{page_id}/children" in url:
            raise requests.RequestException("temporary transport failure")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(pipeline.requests, "get", fake_get)

    assert _select_stale_ready_candidate(page_id) == []


def test_stale_ready_provenance_reads_all_notion_child_pages(monkeypatch):
    page_id = "ready-paginated"
    _install_single_ready_candidate(monkeypatch, page_id)
    child_urls: list[str] = []

    review_block = {
        "id": "review-block",
        "type": "code",
        "code": {
            "language": "markdown",
            "caption": [{"plain_text": pipeline.MANUSCRIPT_CAPTION_REVIEW}],
        },
    }
    ready_block = {
        "id": "ready-block",
        "type": "code",
        "code": {"language": "markdown", "caption": []},
    }

    def fake_get(url, headers=None, timeout=None):
        if f"/v1/pages/{page_id}" in url:
            return _Response(200, _ready_page_payload())
        if f"/v1/blocks/{page_id}/children" in url:
            child_urls.append(url)
            if "start_cursor=" not in url:
                return _Response(
                    200,
                    {
                        "results": [review_block],
                        "has_more": True,
                        "next_cursor": "cursor-2",
                    },
                )
            if "start_cursor=cursor-2" in url:
                return _Response(
                    200,
                    {
                        "results": [ready_block],
                        "has_more": False,
                        "next_cursor": None,
                    },
                )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(pipeline.requests, "get", fake_get)

    assert _select_stale_ready_candidate(page_id) == []
    assert len(child_urls) == 2
