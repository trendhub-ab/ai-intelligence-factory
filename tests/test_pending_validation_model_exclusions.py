from types import SimpleNamespace
from unittest.mock import Mock, patch
import os
import unittest
import pending_retry_validation as lane
import run260_gemini_model_routing as routing
import gemini_temporary_exclusion as exclusion_policy


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
    with patch.dict(os.environ, {exclusion_policy.ENV: "2099-09-16T17:00:00+09:00"}, clear=False):
        lane.install_validation_model_exclusions(p)
        # While the temporary exclusion is active, 3.6 remains unavailable even after
        # Run260 has reinjected its default pool. Surviving models keep revenue-first order.
        assert p.DEEP_DIVE_MODEL_POOL == ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
        assert "gemini-3.6-flash" in p.SESSION_UNAVAILABLE_MODELS
        p._call_deep_dive_pool("repair", kind="quality_retry")
        actual_pool = p._run260_original_call_model_pool.call_args.args[4]
        assert actual_pool == ["gemini-3.5-flash", "gemini-3.7-flash"]


def check_excluded_send(kind, model):
    p = make_pipeline()
    original = p._generate_via_chat
    with patch.dict(os.environ, {exclusion_policy.ENV: "2099-09-16T17:00:00+09:00"}, clear=False):
        lane.install_validation_model_exclusions(p)
        with unittest.TestCase().assertRaisesRegex(RuntimeError, "temporarily excluded"):
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
    p.generate_intelligence_report = Mock(return_value=("draft", "accepted"))
    result = lane.run_pending_retry_lane(p, [{"repo": {"nameWithOwner": "target"}}])
    assert p.generate_intelligence_report.call_args.kwargs["persist_results"] is False
    assert result["quality_passed"] == 1
    assert result["succeeded"] == 1


class ModelExclusionTests(unittest.TestCase):
    def test_routing(self):
        test_exclusion_survives_default_pool_reinjection_and_quality_routing()

    def test_sends(self):
        for kind in ("deep_dive", "quality_retry", "eyecatch_layout"):
            for model in (
                "gemini-3.6-flash",
                "models/gemini-3.6-flash",
                "gemini-3.6-flash-latest",
                "models/GEMINI-3.6-FLASH",
            ):
                with self.subTest(kind=kind, model=model):
                    check_excluded_send(kind, model)

    def test_allowed(self):
        test_allowed_models_keep_original_sender_and_idempotence()

    def test_nonpersistent(self):
        test_validation_article_never_persists_generated_content()

    def test_model_assisted_eyecatch_is_never_sent_in_validation(self):
        p = make_pipeline()
        original = p._generate_via_chat
        lane.install_validation_model_exclusions(p)
        with self.assertRaisesRegex(RuntimeError, "skips model-assisted eyecatch"):
            p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="eyecatch_layout")
        original.assert_not_called()


class TotalValidationBudgetTests(unittest.TestCase):
    def test_provider_visible_fallback_and_repair_share_four_send_ceiling(self):
        p = make_pipeline()
        p.GEMINI_USAGE_AUDIT = SimpleNamespace(records=[])
        original = p._generate_via_chat

        outcomes = [RuntimeError("503"), RuntimeError("503"), "draft", "repair"]

        def provider_attempt(model, prompt, **kwargs):
            p.GEMINI_USAGE_AUDIT.records.append({"model": model, "kind": kwargs.get("request_kind")})
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        original.side_effect = provider_attempt
        lane.install_validation_model_exclusions(p)
        for model in ("gemini-3.8-flash", "gemini-3.7-flash"):
            with self.assertRaisesRegex(RuntimeError, "503"):
                p._generate_via_chat(model, "prompt", request_kind="deep_dive")
        self.assertEqual(p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="deep_dive"), "draft")
        self.assertEqual(p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="quality_retry"), "repair")
        with self.assertRaisesRegex(RuntimeError, "total provider-send ceiling"):
            p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="quality_retry")
        self.assertEqual(original.call_count, 4)
        self.assertEqual(len(p.GEMINI_USAGE_AUDIT.records), 4)

    def test_pre_send_rejection_does_not_consume_provider_send_ceiling(self):
        p = make_pipeline()
        p.GEMINI_USAGE_AUDIT = SimpleNamespace(records=[])
        original = p._generate_via_chat
        first = True

        def sender(model, prompt, **kwargs):
            nonlocal first
            if first:
                first = False
                # Mirrors a local/persistent budget rejection before
                # _consume_gemini_request records a provider-visible attempt.
                raise RuntimeError("pre-send budget rejection")
            p.GEMINI_USAGE_AUDIT.records.append({"model": model, "kind": kwargs.get("request_kind")})
            return "draft"

        original.side_effect = sender
        lane.install_validation_model_exclusions(p)
        with self.assertRaisesRegex(RuntimeError, "pre-send budget rejection"):
            p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="quality_retry")
        self.assertEqual(p._generate_via_chat("gemini-3.5-flash", "prompt", request_kind="quality_retry"), "draft")
        self.assertEqual(len(p.GEMINI_USAGE_AUDIT.records), 1)


if __name__ == "__main__":
    unittest.main()
