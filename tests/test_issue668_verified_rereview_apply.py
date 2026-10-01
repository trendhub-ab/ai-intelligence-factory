from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import member_verified_rereview_apply as apply


def subscriber_state(
    *,
    sync_id="entity:1",
    page_id="sub-page",
    last_reviewed="2026-08-01T00:00:00+00:00",
    score=80,
    status="TEST",
    primary_url="https://github.com/acme/example",
):
    return {
        "sync_id": sync_id,
        "page_id": page_id,
        "last_reviewed": last_reviewed,
        "score": score,
        "status": status,
        "sources": ["GitHub"],
        "primary_url": primary_url,
        "evidence": primary_url,
        "classification": "実務判断",
        "confidence": "高",
        "readiness": "高",
        "name": "private",
    }


def internal_state(
    *,
    last_reviewed="2026-08-01T00:00:00+00:00",
    score=80,
    status="TEST",
):
    return {
        "last_reviewed": last_reviewed,
        "adoption_score": score,
        "adoption_status": status,
    }


class Response:
    def __init__(self, payload=None, status=200):
        self._payload = payload or {}
        self.status_code = status
        self.text = ""
    def json(self):
        return self._payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Issue668Stage2Tests(unittest.TestCase):
    def test_internal_success_patch_only_touches_review_date_and_retry_reason(self):
        with patch.object(apply.requests, "patch", return_value=Response()) as req:
            apply._patch_internal_success("page", "2026-10-01T12:00:00+00:00")
        payload = req.call_args.kwargs["json"]["properties"]
        self.assertEqual(
            set(payload),
            {apply.di.TECH_PROP_LAST_REVIEWED, apply.RETRY_PROP},
        )
        self.assertNotIn(apply.di.TECH_PROP_ADOPTION_SCORE, payload)
        self.assertNotIn(apply.di.TECH_PROP_ADOPTION_STATUS, payload)

    def test_retry_patch_only_touches_private_retry_reason(self):
        with patch.object(apply.requests, "patch", return_value=Response()) as req:
            apply._patch_internal_retry("page", "PRIMARY_SOURCE_UNAVAILABLE", "2026-10-01T12:00:00+00:00")
        payload = req.call_args.kwargs["json"]["properties"]
        self.assertEqual(set(payload), {apply.RETRY_PROP})

    def test_subscriber_patch_only_touches_review_date(self):
        with patch.object(apply.requests, "patch", return_value=Response()) as req:
            apply._patch_subscriber_review_date("sub", "2026-10-01T12:00:00+00:00")
        payload = req.call_args.kwargs["json"]["properties"]
        self.assertEqual(set(payload), {apply.di.SUB_PROP_LAST_REVIEWED})
        self.assertNotIn(apply.di.SUB_PROP_ADOPTION_SCORE, payload)
        self.assertNotIn(apply.di.SUB_PROP_ADOPTION_STATUS, payload)

    def test_retry_property_schema_add_is_idempotent(self):
        with patch.object(apply.di, "NOTION_TECH_DATA_SOURCE_ID", "tech-ds"), patch.object(
            apply.requests,
            "get",
            return_value=Response({"properties": {apply.RETRY_PROP: {"type": "rich_text"}}}),
        ), patch.object(apply.requests, "patch") as p:
            changed = apply._ensure_retry_property()
        self.assertFalse(changed)
        p.assert_not_called()

    def test_retry_property_schema_adds_only_private_field(self):
        with patch.object(apply.di, "NOTION_TECH_DATA_SOURCE_ID", "tech-ds"), patch.object(
            apply.requests, "get", return_value=Response({"properties": {}})
        ), patch.object(
            apply.requests, "patch", return_value=Response()
        ) as p:
            changed = apply._ensure_retry_property()
        self.assertTrue(changed)
        self.assertEqual(
            p.call_args.kwargs["json"],
            {"properties": {apply.RETRY_PROP: {"rich_text": {}}}},
        )

    def test_pass_advances_canonical_then_subscriber_without_decision_mutation(self):
        old = subscriber_state()
        fresh_sub = subscriber_state(last_reviewed="2026-10-01T12:00:00+00:00")
        old_internal = internal_state()
        fresh_internal = internal_state(last_reviewed="2026-10-01T12:00:00+00:00")

        canonical = [
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, fresh_internal),
        ]
        with patch.object(apply.di, "ENABLE_DECISION_INTELLIGENCE_DB", True), patch.object(
            apply.di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"
        ), patch.object(apply, "_ensure_retry_property", return_value=False), patch.object(
            apply, "_read_subscriber_states", side_effect=[[old], [fresh_sub]]
        ), patch.object(
            apply.dry, "select_diverse_stale_queue", side_effect=[([old], 1), ([], 0)]
        ), patch.object(
            apply, "_canonical_state", side_effect=canonical
        ), patch.object(
            apply, "_verify_with_change_outcome",
            return_value={
                "retrieved": True,
                "gate_pass": True,
                "review_safe": True,
                "result": "PASS",
                "change_outcome": "UNCHANGED",
            },
        ), patch.object(
            apply, "_patch_internal_success"
        ) as internal_write, patch.object(
            apply, "_patch_internal_retry"
        ) as retry_write, patch.object(
            apply, "_patch_subscriber_review_date"
        ) as sub_write, patch.object(
            apply, "_get_page", side_effect=[{"id": "sub-page"}, {"id": "sub-page"}]
        ), patch.object(
            apply.member, "_source_state", side_effect=[old, fresh_sub]
        ), patch.dict(apply.os.environ, {}, clear=False):
            for key in apply.MODEL_ENV_KEYS:
                apply.os.environ.pop(key, None)
            result = apply.run_apply(
                as_of=apply.date(2026, 10, 1),
                limit=5,
                stale_days=30,
                verified_at="2026-10-01T12:00:00+00:00",
            )

        internal_write.assert_called_once()
        retry_write.assert_not_called()
        sub_write.assert_called_once()
        self.assertEqual(result["canonical_dates_advanced"], 1)
        self.assertEqual(result["subscriber_dates_advanced"], 1)
        self.assertEqual(result["backlog_reduced_by"], 1)
        self.assertEqual(result["decision_mutations"], 0)
        self.assertEqual(result["score_mutations"], 0)
        self.assertEqual(result["model_calls"], 0)

    def test_unavailable_keeps_review_date_and_writes_private_retry_only(self):
        old = subscriber_state()
        old_internal = internal_state()
        canonical = [
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
        ]
        with patch.object(apply.di, "ENABLE_DECISION_INTELLIGENCE_DB", True), patch.object(
            apply.di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"
        ), patch.object(apply, "_ensure_retry_property", return_value=False), patch.object(
            apply, "_read_subscriber_states", side_effect=[[old], [old]]
        ), patch.object(
            apply.dry, "select_diverse_stale_queue", side_effect=[([old], 1), ([old], 1)]
        ), patch.object(
            apply, "_canonical_state", side_effect=canonical
        ), patch.object(
            apply, "_verify_with_change_outcome",
            return_value={
                "retrieved": False,
                "gate_pass": False,
                "review_safe": False,
                "result": "UNAVAILABLE",
                "change_outcome": "NOT_CHECKED",
            },
        ), patch.object(
            apply, "_patch_internal_success"
        ) as internal_write, patch.object(
            apply, "_patch_internal_retry"
        ) as retry_write, patch.object(
            apply, "_patch_subscriber_review_date"
        ) as sub_write, patch.dict(apply.os.environ, {}, clear=False):
            for key in apply.MODEL_ENV_KEYS:
                apply.os.environ.pop(key, None)
            result = apply.run_apply(
                as_of=apply.date(2026, 10, 1),
                limit=5,
                stale_days=30,
                verified_at="2026-10-01T12:00:00+00:00",
            )

        internal_write.assert_not_called()
        sub_write.assert_not_called()
        retry_write.assert_called_once()
        self.assertEqual(result["canonical_dates_advanced"], 0)
        self.assertEqual(result["subscriber_dates_advanced"], 0)
        self.assertEqual(result["retry_reasons_written"], 1)
        self.assertEqual(result["backlog_reduced_by"], 0)

    def test_canonical_mismatch_fails_closed_without_write(self):
        old = subscriber_state()
        mismatched_internal = internal_state(score=81)
        with patch.object(apply.di, "ENABLE_DECISION_INTELLIGENCE_DB", True), patch.object(
            apply.di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"
        ), patch.object(apply, "_ensure_retry_property", return_value=False), patch.object(
            apply, "_read_subscriber_states", side_effect=[[old], [old]]
        ), patch.object(
            apply.dry, "select_diverse_stale_queue", side_effect=[([old], 1), ([old], 1)]
        ), patch.object(
            apply, "_canonical_state", return_value=({"id": "tech-page"}, mismatched_internal)
        ), patch.object(apply, "_patch_internal_success") as internal_write, patch.object(
            apply, "_patch_internal_retry"
        ) as retry_write, patch.object(
            apply, "_patch_subscriber_review_date"
        ) as sub_write, patch.dict(apply.os.environ, {}, clear=False):
            for key in apply.MODEL_ENV_KEYS:
                apply.os.environ.pop(key, None)
            result = apply.run_apply(
                as_of=apply.date(2026, 10, 1),
                limit=5,
                stale_days=30,
                verified_at="2026-10-01T12:00:00+00:00",
            )

        internal_write.assert_not_called()
        retry_write.assert_not_called()
        sub_write.assert_not_called()
        self.assertEqual(result["canonical_mismatch"], 1)


    def test_material_change_never_advances_review_date(self):
        old = subscriber_state()
        old_internal = internal_state()
        canonical = [
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
        ]
        with patch.object(apply.di, "ENABLE_DECISION_INTELLIGENCE_DB", True), patch.object(
            apply.di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"
        ), patch.object(apply, "_ensure_retry_property", return_value=False), patch.object(
            apply, "_read_subscriber_states", side_effect=[[old], [old]]
        ), patch.object(
            apply.dry, "select_diverse_stale_queue", side_effect=[([old], 1), ([old], 1)]
        ), patch.object(
            apply, "_canonical_state", side_effect=canonical
        ), patch.object(
            apply, "_verify_with_change_outcome",
            return_value={
                "retrieved": True,
                "gate_pass": True,
                "review_safe": False,
                "result": "PASS",
                "change_outcome": "MATERIAL_CHANGE",
            },
        ), patch.object(
            apply, "_patch_internal_success"
        ) as internal_write, patch.object(
            apply, "_patch_internal_retry"
        ) as retry_write, patch.object(
            apply, "_patch_subscriber_review_date"
        ) as sub_write, patch.dict(apply.os.environ, {}, clear=False):
            for key in apply.MODEL_ENV_KEYS:
                apply.os.environ.pop(key, None)
            result = apply.run_apply(
                as_of=apply.date(2026, 10, 1),
                limit=5,
                stale_days=30,
                verified_at="2026-10-01T12:00:00+00:00",
            )

        internal_write.assert_not_called()
        sub_write.assert_not_called()
        retry_write.assert_called_once()
        self.assertEqual(
            retry_write.call_args.args[1],
            "MATERIAL_CHANGE_REQUIRES_DECISION_REVIEW",
        )
        self.assertEqual(result["material_change"], 1)
        self.assertEqual(result["canonical_dates_advanced"], 0)

    def test_no_evidence_baseline_never_advances_review_date(self):
        old = subscriber_state()
        old_internal = internal_state()
        canonical = [
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
            ({"id": "tech-page"}, old_internal),
        ]
        with patch.object(apply.di, "ENABLE_DECISION_INTELLIGENCE_DB", True), patch.object(
            apply.di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"
        ), patch.object(apply, "_ensure_retry_property", return_value=False), patch.object(
            apply, "_read_subscriber_states", side_effect=[[old], [old]]
        ), patch.object(
            apply.dry, "select_diverse_stale_queue", side_effect=[([old], 1), ([old], 1)]
        ), patch.object(
            apply, "_canonical_state", side_effect=canonical
        ), patch.object(
            apply, "_verify_with_change_outcome",
            return_value={
                "retrieved": True,
                "gate_pass": True,
                "review_safe": False,
                "result": "PASS",
                "change_outcome": "NO_BASELINE",
            },
        ), patch.object(
            apply, "_patch_internal_success"
        ) as internal_write, patch.object(
            apply, "_patch_internal_retry"
        ) as retry_write, patch.object(
            apply, "_patch_subscriber_review_date"
        ) as sub_write, patch.dict(apply.os.environ, {}, clear=False):
            for key in apply.MODEL_ENV_KEYS:
                apply.os.environ.pop(key, None)
            result = apply.run_apply(
                as_of=apply.date(2026, 10, 1),
                limit=5,
                stale_days=30,
                verified_at="2026-10-01T12:00:00+00:00",
            )

        internal_write.assert_not_called()
        sub_write.assert_not_called()
        retry_write.assert_called_once()
        self.assertEqual(retry_write.call_args.args[1], "NO_EVIDENCE_BASELINE")
        self.assertEqual(result["no_baseline"], 1)
        self.assertEqual(result["canonical_dates_advanced"], 0)

    def test_model_credentials_fail_closed_before_any_write(self):
        with patch.object(apply, "_ensure_retry_property") as ensure, patch.dict(
            apply.os.environ, {"GEMINI_API_KEY": "secret"}, clear=False
        ):
            with self.assertRaises(RuntimeError):
                apply.run_apply(
                    as_of=apply.date(2026, 10, 1),
                    limit=5,
                    stale_days=30,
                    verified_at="2026-10-01T12:00:00+00:00",
                )
        ensure.assert_not_called()


    def test_verified_ledger_baseline_allows_review_date_advancement(self):
        state = subscriber_state()
        fake_pipeline = types.SimpleNamespace(
            EVIDENCE_SUPPLEMENT_REQUIRED="SUPPLEMENT_REQUIRED",
            EVIDENCE_INSUFFICIENT="INSUFFICIENT",
            prepare_source_context=lambda repo: {
                "evidence_documents": [{
                    "retrieved": True,
                    "url": "https://github.com/acme/example",
                    "resolved_url": "https://github.com/acme/example",
                    "document_text": "stable prior extract plus current details",
                }],
                "verification_context": "stable prior extract plus current details",
            },
            assess_evidence_sufficiency=lambda source_info: {
                "state": "SUFFICIENT",
                "decision_scope_safe": True,
            },
            supplement_source_evidence=lambda source_info: source_info,
            _primary_source_authority_failures=lambda source_info: [],
        )
        snapshot = {
            "url": "https://github.com/acme/example",
            "resolved_url": "https://github.com/acme/example",
            "document_hash": "old",
            "extract": "stable prior extract",
        }
        with patch.dict(sys.modules, {"pipeline": fake_pipeline}), patch.object(
            apply, "_query_active_primary_snapshots", return_value=[snapshot]
        ), patch.object(
            apply.evidence_ledger,
            "check_health",
            return_value={"health": "VERIFIED", "material": False},
        ):
            result = apply._verify_with_change_outcome(state, "entity:1")
        self.assertTrue(result["gate_pass"])
        self.assertTrue(result["review_safe"])
        self.assertEqual(result["change_outcome"], "UNCHANGED")

    def test_ledger_material_change_blocks_review_date_advancement(self):
        state = subscriber_state()
        fake_pipeline = types.SimpleNamespace(
            EVIDENCE_SUPPLEMENT_REQUIRED="SUPPLEMENT_REQUIRED",
            EVIDENCE_INSUFFICIENT="INSUFFICIENT",
            prepare_source_context=lambda repo: {
                "evidence_documents": [{
                    "retrieved": True,
                    "url": "https://github.com/acme/example",
                    "resolved_url": "https://github.com/acme/example",
                    "document_text": "materially different current document",
                }],
                "verification_context": "materially different current document",
            },
            assess_evidence_sufficiency=lambda source_info: {
                "state": "SUFFICIENT",
                "decision_scope_safe": True,
            },
            supplement_source_evidence=lambda source_info: source_info,
            _primary_source_authority_failures=lambda source_info: [],
        )
        snapshot = {
            "url": "https://github.com/acme/example",
            "resolved_url": "https://github.com/acme/example",
            "document_hash": "old",
            "extract": "old decision evidence",
        }
        with patch.dict(sys.modules, {"pipeline": fake_pipeline}), patch.object(
            apply, "_query_active_primary_snapshots", return_value=[snapshot]
        ), patch.object(
            apply.evidence_ledger,
            "check_health",
            return_value={"health": "MATERIAL_CHANGE", "material": True},
        ):
            result = apply._verify_with_change_outcome(state, "entity:1")
        self.assertTrue(result["gate_pass"])
        self.assertFalse(result["review_safe"])
        self.assertEqual(result["change_outcome"], "MATERIAL_CHANGE")

    def test_retry_codes_are_private_generic_categories(self):
        state = subscriber_state(primary_url="")
        self.assertEqual(
            apply._retry_code(state, {"result": "UNAVAILABLE"}),
            "MISSING_PRIMARY_SOURCE",
        )
        state = subscriber_state()
        self.assertEqual(
            apply._retry_code(state, {"result": "EVIDENCE_FAIL", "change_outcome": "NOT_CHECKED"}),
            "EVIDENCE_GATE_FAILED",
        )
        self.assertEqual(
            apply._retry_code(state, {"result": "PASS", "change_outcome": "MATERIAL_CHANGE"}),
            "MATERIAL_CHANGE_REQUIRES_DECISION_REVIEW",
        )
        self.assertEqual(
            apply._retry_code(state, {"result": "PASS", "change_outcome": "NO_BASELINE"}),
            "NO_EVIDENCE_BASELINE",
        )
        self.assertEqual(
            apply._retry_code(state, {"result": "UNAVAILABLE", "change_outcome": "NOT_CHECKED"}),
            "PRIMARY_SOURCE_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
