from types import SimpleNamespace
from unittest.mock import Mock
import unittest
import pending_retry_validation as lane
import run260_gemini_model_routing as routing


def make_pipeline():
    return SimpleNamespace(
        DEEP_DIVE_MODEL_POOL=["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"],
        DEEP_DIVE_MODEL_CANDIDATES=[],
        SCREENING_MODEL_POOL=["gemini-3.5-flash-lite"],
        SESSION_UNAVAILABLE_MODELS=set(),
        _generate_via_chat=Mock(return_value="draft"),
        _call_model_pool=Mock(),
        _call_deep_dive_pool=Mock(),
        NoAvailableModelError=RuntimeError,
        logger=Mock(),
    )


def test_exclusion_survives_default_pool_reinjection_and_quality_routing():
    p = make_pipeline()
    routing.install(p)
    assert "gemini-3.6-flash" in p.DEEP_DIVE_MODEL_POOL
    lane.install_validation_model_exclusions(p)
    assert p.DEEP_DIVE_MODEL_POOL == ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"]
    assert "gemini-3.6-flash" in p.SESSION_UNAVAILABLE_MODELS
    p._call_deep_dive_pool("repair", kind="quality_retry")
    actual_pool = p._run260_original_call_model_pool.call_args.args[4]
    assert actual_pool == ["gemini-3.7-flash", "gemini-3.5-flash"]


def check_excluded_send(kind, model):
    p = make_pipeline()
    original = p._generate_via_chat
    lane.install_validation_model_exclusions(p)
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "Operator excluded"):
        p._generate_via_chat(model, "prompt", request_kind=kind)
    original.assert_not_called()


def test_allowed_models_keep_original_sender_and_idempotence():
    p = make_pipeline()
    original = p._generate_via_chat
    lane.install_validation_model_exclusions(p)
    guard = p._generate_via_chat
    lane.install_validation_model_exclusions(p)
    assert p._generate_via_chat is guard
    for model in p.DEEP_DIVE_MODEL_POOL:
        assert p._generate_via_chat(model, "prompt") == "draft"
    assert original.call_count == 3


def test_validation_article_never_persists_generated_content():
    p = make_pipeline()
    p.PENDING_RETRY_REQUEST_BUDGET = SimpleNamespace(can_request=lambda: True)
    p.DEEP_DIVE_MODEL_BUDGET = SimpleNamespace(can_request=lambda: True)
    p.GEMINI_BUDGET = SimpleNamespace(can_request=lambda: True)
    p._model_pool_has_session_candidate = lambda pool: True
    p.generate_intelligence_report = Mock(return_value="draft")
    lane.run_pending_retry_lane(p, [{"repo": {"nameWithOwner": "target"}}])
    assert p.generate_intelligence_report.call_args.kwargs["persist_results"] is False

class ModelExclusionTests(unittest.TestCase):
    def test_routing(self):
        test_exclusion_survives_default_pool_reinjection_and_quality_routing()

    def test_sends(self):
        for kind in ("deep_dive", "quality_retry", "eyecatch_layout"):
            for model in ("gemini-3.6-flash", "models/gemini-3.6-flash"):
                with self.subTest(kind=kind, model=model):
                    check_excluded_send(kind, model)

    def test_allowed(self):
        test_allowed_models_keep_original_sender_and_idempotence()

    def test_nonpersistent(self):
        test_validation_article_never_persists_generated_content()
