import json
from types import SimpleNamespace

import article_revalidation
import production_pipeline


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Response:
    def __init__(self, article_status, content_status, status_code=200):
        self.status_code = status_code
        self._article_status = article_status
        self._content_status = content_status

    def json(self):
        return {
            "properties": {
                "Article Status": {"select": {"name": self._article_status}},
                "Content Status": {"select": {"name": self._content_status}},
            }
        }


def _selector_pipeline():
    rows = [
        {"notion_page_id": "ready", "repo": {"nameWithOwner": "ready"}},
        {"notion_page_id": "review", "repo": {"nameWithOwner": "review"}},
        {"notion_page_id": "quality", "repo": {"nameWithOwner": "quality"}},
        {"notion_page_id": "pending", "repo": {"nameWithOwner": "pending"}},
    ]
    statuses = {
        "ready": ("Ready", "Deep Dive"),
        "review": ("Needs Editorial Review", "Deep Dive"),
        "quality": ("Not Planned", "Quality Failed"),
        "pending": ("Not Planned", "Pending Retry"),
    }

    class _Requests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            page_id = url.rsplit("/", 1)[-1]
            return _Response(*statuses[page_id])

    calls = []

    def get_regen_test_items(limit, source):
        calls.append((limit, source))
        return rows

    pipeline = SimpleNamespace(
        requests=_Requests,
        _notion_headers=lambda: {"Authorization": "test"},
        get_regen_test_items=get_regen_test_items,
        logger=_Logger(),
        PROP_ARTICLE_STATUS="Article Status",
        PROP_CONTENT_STATUS="Content Status",
        ARTICLE_STATUS_READY="Ready",
        ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW="Needs Editorial Review",
        CONTENT_STATUS_PENDING_RETRY="Pending Retry",
        CONTENT_STATUS_QUALITY_FAILED="Quality Failed",
    )
    return pipeline, calls


def test_selector_bypasses_acquisition_dedup_but_excludes_ready_and_pending():
    pipeline, calls = _selector_pipeline()
    selected = article_revalidation.select_revalidation_items(pipeline, limit=2)

    assert calls == [(100, "")]
    assert [row["notion_page_id"] for row in selected] == ["review", "quality"]
    assert selected[0]["revalidation_article_status"] == "Needs Editorial Review"
    assert selected[1]["revalidation_content_status"] == "Quality Failed"


def test_pending_only_selector_isolates_pending_retry():
    pipeline, calls = _selector_pipeline()
    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        pending_only=True,
    )

    assert calls == [(100, "")]
    assert [row["notion_page_id"] for row in selected] == ["pending"]
    assert selected[0]["revalidation_article_status"] == "Not Planned"
    assert selected[0]["revalidation_content_status"] == "Pending Retry"


def test_revalidation_is_read_only_and_bounded(monkeypatch):
    generated_calls = []

    class DailyQuotaExhaustedError(Exception):
        pass

    pipeline = SimpleNamespace(
        logger=_Logger(),
        DEEP_DIVE_MODEL_BUDGET=SimpleNamespace(budget=12),
        legal_safety_gate=lambda repo: (True, "SAFE"),
        generate_intelligence_report=lambda repo, **kwargs: generated_calls.append((repo, kwargs)) or ("manuscript", "accepted"),
        DailyQuotaExhaustedError=DailyQuotaExhaustedError,
    )
    selected = [{
        "notion_page_id": "review",
        "repo": {"nameWithOwner": "vendor/project"},
        "screening_score": 88,
        "screening_reason": "high value",
        "revalidation_article_status": "Needs Editorial Review",
        "revalidation_content_status": "Deep Dive",
    }]
    monkeypatch.setenv("ARTICLE_REVALIDATION_REQUEST_BUDGET", "4")
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", lambda *args, **kwargs: selected)

    result = article_revalidation.run_article_revalidation(pipeline, limit=1)

    assert result == {"selected": 1, "generated": 1, "accepted": 1, "rejected": 0}
    assert pipeline.DEEP_DIVE_MODEL_BUDGET.budget == 4
    assert len(generated_calls) == 1
    kwargs = generated_calls[0][1]
    assert kwargs["persist_results"] is False
    assert kwargs["notion_page_id"] == "review"
    assert kwargs["candidate_origin"] == "article_revalidation"


def test_pending_retry_validation_is_read_only_and_uses_pending_origin(monkeypatch):
    generated_calls = []

    class DailyQuotaExhaustedError(Exception):
        pass

    pipeline = SimpleNamespace(
        logger=_Logger(),
        DEEP_DIVE_MODEL_BUDGET=SimpleNamespace(budget=12),
        legal_safety_gate=lambda repo: (True, "SAFE"),
        generate_intelligence_report=lambda repo, **kwargs: generated_calls.append((repo, kwargs)) or ("manuscript", "accepted"),
        DailyQuotaExhaustedError=DailyQuotaExhaustedError,
    )
    selected = [{
        "notion_page_id": "pending",
        "repo": {"nameWithOwner": "vendor/project"},
        "screening_score": 88,
        "screening_reason": "high value",
        "revalidation_article_status": "Not Planned",
        "revalidation_content_status": "Pending Retry",
    }]
    monkeypatch.setenv("ARTICLE_REVALIDATION_REQUEST_BUDGET", "3")

    def selector(*args, **kwargs):
        assert kwargs["pending_only"] is True
        assert kwargs["include_quality_failed"] is False
        return selected

    monkeypatch.setattr(article_revalidation, "select_revalidation_items", selector)

    result = article_revalidation.run_article_revalidation(
        pipeline,
        limit=1,
        pending_only=True,
    )

    assert result == {"selected": 1, "generated": 1, "accepted": 1, "rejected": 0}
    assert pipeline.DEEP_DIVE_MODEL_BUDGET.budget == 3
    kwargs = generated_calls[0][1]
    assert kwargs["persist_results"] is False
    assert kwargs["notion_page_id"] == "pending"
    assert kwargs["candidate_origin"] == "pending_retry_validation"


def test_workflow_dispatch_mode_reads_github_event(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"inputs": {"mode": "article_validation"}}), encoding="utf-8")
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    assert production_pipeline._workflow_dispatch_mode() == "article_validation"


def test_explicit_mode_is_testable_without_github_event(monkeypatch):
    monkeypatch.setenv("AIIF_ONE_SHOT_MODE", "article_validation")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    assert production_pipeline._workflow_dispatch_mode() == "article_validation"


def test_pending_retry_mode_is_testable_without_github_event(monkeypatch):
    monkeypatch.setenv("AIIF_ONE_SHOT_MODE", "pending_retry_validation")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    assert production_pipeline._workflow_dispatch_mode() == "pending_retry_validation"


def test_normal_execution_does_not_accidentally_enter_validation(monkeypatch):
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    assert production_pipeline._workflow_dispatch_mode() == ""
