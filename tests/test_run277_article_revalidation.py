import json
from types import SimpleNamespace
from unittest.mock import patch

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
        {"notion_page_id": "ready-current", "repo": {"nameWithOwner": "ready-current"}},
        {"notion_page_id": "ready-stale", "repo": {"nameWithOwner": "ready-stale"}},
        {"notion_page_id": "review", "repo": {"nameWithOwner": "review"}},
        {"notion_page_id": "quality", "repo": {"nameWithOwner": "quality"}},
        {"notion_page_id": "pending", "repo": {"nameWithOwner": "pending"}},
    ]
    statuses = {
        "ready-current": ("Ready", "Deep Dive"),
        "ready-stale": ("Ready", "Deep Dive"),
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
        _notion_page_has_manuscript_child=lambda page_id, headers: page_id == "ready-current",
    )
    return pipeline, calls


def test_selector_bypasses_acquisition_dedup_but_excludes_ready_and_pending():
    pipeline, calls = _selector_pipeline()
    selected = article_revalidation.select_revalidation_items(pipeline, limit=2)

    assert calls == [(100, "")]
    assert [row["notion_page_id"] for row in selected] == ["review", "quality"]
    assert selected[0]["revalidation_article_status"] == "Needs Editorial Review"
    assert selected[1]["revalidation_content_status"] == "Quality Failed"


def test_editorial_priority_avoids_unneeded_ready_provenance_reads():
    pipeline, _ = _selector_pipeline()
    proof_calls = []

    def must_not_run(page_id, headers):
        proof_calls.append(page_id)
        raise AssertionError("Ready provenance should not be read when editorial fills the limit")

    pipeline._notion_page_has_manuscript_child = must_not_run
    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        include_stale_ready=True,
    )

    assert [row["notion_page_id"] for row in selected] == ["review"]
    assert proof_calls == []


def test_selector_includes_only_stale_ready_when_explicitly_enabled():
    pipeline, calls = _selector_pipeline()
    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=3,
        include_stale_ready=True,
    )

    assert calls == [(100, "")]
    assert [row["notion_page_id"] for row in selected] == ["review", "ready-stale", "quality"]
    stale = selected[1]
    assert stale["revalidation_article_status"] == "Ready"
    assert stale["revalidation_stale_ready"] is True


def test_stale_ready_can_be_preferred_for_ready_rescue():
    pipeline, _ = _selector_pipeline()
    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        include_stale_ready=True,
        prefer_stale_ready=True,
    )

    assert [row["notion_page_id"] for row in selected] == ["ready-stale"]
    assert selected[0]["revalidation_stale_ready"] is True


def test_stale_ready_preference_bounds_provenance_probes_before_editorial_fallback():
    rows = [
        {"notion_page_id": f"ready-{index}", "repo": {"nameWithOwner": f"ready-{index}"}}
        for index in range(8)
    ] + [{"notion_page_id": "review", "repo": {"nameWithOwner": "review"}}]

    class _Requests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            page_id = url.rsplit("/", 1)[-1]
            article = "Needs Editorial Review" if page_id == "review" else "Ready"
            return _Response(article, "Deep Dive")

    proof_calls = []
    pipeline = SimpleNamespace(
        requests=_Requests,
        _notion_headers=lambda: {"Authorization": "test"},
        get_regen_test_items=lambda limit, source: rows,
        logger=_Logger(),
        PROP_ARTICLE_STATUS="Article Status",
        PROP_CONTENT_STATUS="Content Status",
        ARTICLE_STATUS_READY="Ready",
        ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW="Needs Editorial Review",
        CONTENT_STATUS_PENDING_RETRY="Pending Retry",
        CONTENT_STATUS_QUALITY_FAILED="Quality Failed",
        _notion_page_has_manuscript_child=lambda page_id, headers: proof_calls.append(page_id) or True,
    )

    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        include_stale_ready=True,
        prefer_stale_ready=True,
    )

    assert [row["notion_page_id"] for row in selected] == ["review"]
    assert proof_calls == [f"ready-{index}" for index in range(5)]


def test_stale_ready_provenance_uncertainty_fails_closed():
    pipeline, _ = _selector_pipeline()
    del pipeline._notion_page_has_manuscript_child

    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=3,
        include_stale_ready=True,
    )

    assert [row["notion_page_id"] for row in selected] == ["review", "quality"]


def test_stale_ready_provenance_exception_fails_closed():
    pipeline, _ = _selector_pipeline()

    def broken_proof(page_id, headers):
        raise RuntimeError("proof unavailable")

    pipeline._notion_page_has_manuscript_child = broken_proof
    selected = article_revalidation.select_revalidation_items(
        pipeline,
        limit=3,
        include_stale_ready=True,
    )

    assert [row["notion_page_id"] for row in selected] == ["review", "quality"]


def test_existing_recovery_persists_stale_ready_with_dedicated_origin(monkeypatch):
    generated_calls = []

    class _Budget:
        budget = 12
        def can_request(self):
            return True

    class _DailyQuotaExhaustedError(Exception):
        pass

    stale = {
        "notion_page_id": "ready-stale",
        "repo": {"nameWithOwner": "ready-stale"},
        "screening_score": 81,
        "screening_reason": "current policy stale",
        "revalidation_article_status": "Ready",
        "revalidation_content_status": "Deep Dive",
        "revalidation_stale_ready": True,
    }
    pipeline = SimpleNamespace(
        logger=_Logger(),
        TOP_N_FOR_DEEP_DIVE=3,
        NOTION_API_KEY="test",
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["m1"],
        _model_pool_has_session_candidate=lambda pool: True,
        legal_safety_gate=lambda repo: (True, "SAFE"),
        generate_intelligence_report=lambda repo, **kwargs: generated_calls.append((repo, kwargs)) or "report",
        DailyQuotaExhaustedError=_DailyQuotaExhaustedError,
        _READY_RESCUE_ACTIVE=True,
    )
    seen = {}

    def select(*args, **kwargs):
        seen.update(kwargs)
        return [stale]

    monkeypatch.setattr(article_revalidation, "select_revalidation_items", select)

    generated_count, next_rank = article_revalidation.run_existing_editorial_recovery(
        pipeline,
        generated_count=0,
        next_candidate_rank=4,
        limit=1,
    )

    assert generated_count == 1
    assert next_rank == 5
    assert seen["include_stale_ready"] is True
    assert seen["prefer_stale_ready"] is True
    kwargs = generated_calls[0][1]
    assert kwargs["persist_results"] is True
    assert kwargs["candidate_origin"] == "existing_stale_ready_recovery"



def test_existing_recovery_keeps_editorial_priority_outside_ready_rescue(monkeypatch):
    class _Budget:
        budget = 12
        def can_request(self):
            return True

    pipeline = SimpleNamespace(
        logger=_Logger(),
        TOP_N_FOR_DEEP_DIVE=3,
        NOTION_API_KEY="test",
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["m1"],
        _model_pool_has_session_candidate=lambda pool: True,
    )
    seen = {}

    def select(*args, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(article_revalidation, "select_revalidation_items", select)
    generated_count, next_rank = article_revalidation.run_existing_editorial_recovery(
        pipeline,
        generated_count=0,
        next_candidate_rank=4,
        limit=1,
    )

    assert (generated_count, next_rank) == (0, 4)
    assert seen["include_stale_ready"] is True
    assert seen["prefer_stale_ready"] is False


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

    assert result == {"selected": 1, "generated": 1, "accepted": 1, "rejected": 0, "unverified": 0}
    assert pipeline.DEEP_DIVE_MODEL_BUDGET.budget == 4
    assert len(generated_calls) == 1
    kwargs = generated_calls[0][1]
    assert kwargs["persist_results"] is False
    assert kwargs["notion_page_id"] == "review"
    assert kwargs["candidate_origin"] == "article_revalidation"


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


def test_normal_execution_does_not_accidentally_enter_validation(monkeypatch):
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    assert production_pipeline._workflow_dispatch_mode() == ""


def test_exact_target_selects_only_exact_existing_name_and_fails_closed(monkeypatch):
    pipeline, _ = _selector_pipeline()
    rows = [
        {"notion_page_id": "a", "repo": {"nameWithOwner": "OpenAI doesn't cryptographically sign its API responses"}},
        {"notion_page_id": "b", "repo": {"nameWithOwner": "NemotronLabs VoiceChat"}},
    ]
    pipeline.get_regen_test_items = lambda limit, source: rows
    pipeline.requests.get = lambda url, headers=None, timeout=None: _Response("Needs Editorial Review", "Deep Dive")
    selected = article_revalidation.select_revalidation_items(
        pipeline, limit=1, exact_target="OpenAI doesn't cryptographically sign its API responses"
    )
    assert [x["notion_page_id"] for x in selected] == ["a"]
    assert article_revalidation.select_revalidation_items(
        pipeline, limit=1, exact_target="OpenAI"
    ) == []


def test_exact_target_env_is_forwarded_by_revalidation(monkeypatch):
    class DailyQuotaExhaustedError(Exception):
        pass
    pipeline = SimpleNamespace(logger=_Logger(), DEEP_DIVE_MODEL_BUDGET=SimpleNamespace(budget=12))
    seen = {}
    def select(*args, **kwargs):
        seen.update(kwargs)
        return []
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", select)
    monkeypatch.setenv("ARTICLE_REVALIDATION_EXACT_TARGET", "target-name")
    article_revalidation.run_article_revalidation(pipeline, limit=1)
    assert seen["exact_target"] == "target-name"
