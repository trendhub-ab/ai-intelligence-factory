import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import external_product_review_import as ext


VALID_REVIEW = {
    "category": "AGENT",
    "adoption_score": 80,
    "components": {
        "Evidence Quality": 22,
        "Production Maturity": 20,
        "Use-case Utility / Fit": 17,
        "Reliability / Security Risk": 11,
        "Integration / Migration Feasibility": 7,
        "Ecosystem / Support Durability": 3,
    },
    "adoption_status": "TEST",
    "evidence_confidence": "HIGH",
    "production_readiness": "MEDIUM",
    "main_risk": "運用時の権限設計と外部ツール接続範囲を事前に確認する必要がある。",
    "best_for": "複数ステップのAIワークフローを検証したい開発チーム。",
    "avoid_for": "単純な一回限りのテキスト生成だけを必要とする用途。",
    "short_rationale": "一次情報でエージェント実行機能と開発向け統合が確認できるため。",
    "japanese_display_label": "Example Agent — AIエージェント開発基盤",
    "next_review_days": 30,
}

ROW = {
    "source": "GitHub",
    "name": "example/agent",
    "url": "https://github.com/example/agent",
    "description": "Example agent framework",
    "review": VALID_REVIEW,
}


class Run153ExternalReviewImportTests(unittest.TestCase):
    def test_runtime_gemini_guard_is_fail_closed(self):
        with self.assertRaises(RuntimeError):
            ext._forbid_gemini("anything")

    def test_invalid_component_sum_rejected_by_production_validator(self):
        bad = dict(VALID_REVIEW)
        bad["components"] = dict(VALID_REVIEW["components"])
        bad["components"]["Ecosystem / Support Durability"] = 2
        with self.assertRaises(ValueError):
            ext.pipeline._parse_product_review_response(bad)

    @patch.object(ext, "_prepare_verified_evidence")
    @patch.object(ext.pipeline, "persist_decision_intelligence_assessment")
    def test_validate_mode_never_persists(self, persist, prepare):
        prepare.return_value = (
            {"context": "verified", "verification_context": "verified", "evidence_metadata": {}},
            {"state": "SUFFICIENT", "decision_scope_safe": True},
            [],
        )
        with patch.object(ext, "_validate_review_against_evidence", return_value=(True, [])):
            result = ext.process_row(ROW, apply=False)
        self.assertEqual(result["status"], "validated")
        persist.assert_not_called()

    @patch.object(ext, "_prepare_verified_evidence")
    def test_explicit_eol_context_blocks_positive_adoption_before_evidence_fetch(self, prepare):
        row = json.loads(json.dumps(ROW, ensure_ascii=False))
        row["decision_context"] = {
            "plain_summary": "このプロジェクトは従来のAIエージェント基盤です。公式一次情報でリポジトリがArchivedになったことを明示しています。",
            "topic_trigger": "Archived後の新規導入可否を再評価し、現在の保守状況と移行判断を会員向けに明確化します。",
        }
        row["review"]["adoption_status"] = "ADOPT"
        row["review"]["production_readiness"] = "HIGH"
        result = ext.process_row(row, apply=True)
        self.assertEqual(result["status"], "invalid_lifecycle_consistency")
        self.assertFalse(result["saved"])
        self.assertTrue(any("lifecycle contradiction" in f for f in result["failures"]))
        prepare.assert_not_called()

    def test_explicit_eol_context_allows_avoid_low(self):
        row = json.loads(json.dumps(ROW, ensure_ascii=False))
        row["decision_context"] = {
            "plain_summary": "このプロジェクトは従来のAIエージェント基盤です。公式一次情報でリポジトリがArchivedになったことを明示しています。",
            "topic_trigger": "Archived後は新規採用ではなく既存資産の移行判断として評価します。",
        }
        row["review"]["adoption_status"] = "AVOID"
        row["review"]["production_readiness"] = "LOW"
        parsed = ext.pipeline._parse_product_review_response(row["review"])
        self.assertEqual([], ext.validate_lifecycle_consistency(row, parsed))

    @patch.object(ext, "_prepare_verified_evidence")
    def test_insufficient_evidence_fails_before_write(self, prepare):
        prepare.return_value = (
            {"context": ""},
            {"state": ext.pipeline.EVIDENCE_INSUFFICIENT, "decision_scope_safe": False, "blocking_missing": ["primary_source_resolved"]},
            [],
        )
        result = ext.process_row(ROW, apply=True)
        self.assertEqual(result["status"], "skipped_evidence")
        self.assertFalse(result["saved"])

    @patch.object(ext, "_prepare_verified_evidence")
    @patch.object(ext.pipeline, "persist_decision_intelligence_assessment")
    def test_apply_uses_existing_persistence_path(self, persist, prepare):
        prepare.return_value = (
            {"context": "verified", "verification_context": "verified", "evidence_metadata": {}},
            {"state": "SUFFICIENT", "decision_scope_safe": True},
            [],
        )
        persist.return_value = {"saved": True, "created": True, "entity_id": "github:example/agent", "page_id": "p1"}
        with patch.object(ext, "_validate_review_against_evidence", return_value=(True, [])):
            result = ext.process_row(ROW, apply=True)
        self.assertTrue(result["saved"])
        self.assertTrue(result["created"])
        persist.assert_called_once()

    def test_apply_cli_requires_explicit_confirmation(self):
        with patch("sys.argv", ["external_product_review_import.py", "apply", "--input", "x.json"]):
            with self.assertRaises(SystemExit) as ctx:
                ext.main()
        self.assertIn(ext.CONFIRM_TOKEN, str(ctx.exception))

    @patch.object(ext.context_first_enrichment, "preflight_context_first_schema")
    @patch.object(ext.decision_intelligence, "preflight_decision_intelligence_schema")
    @patch.object(ext, "_assessed_snapshot", return_value={})
    @patch.object(ext, "_assessed_count", side_effect=[26, 27])
    @patch.object(ext, "process_row", return_value={"name": "example/agent", "status": "saved", "saved": True, "created": True})
    @patch.object(ext.context_first_enrichment, "enrich_context_first", return_value={"enabled": True, "zero_gemini_calls": True})
    def test_run_writes_audit_and_enriches_after_save(self, enrich, process, count, snapshot, di_pre, ctx_pre):
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "reviews.json"
            audit_path = Path(td) / "audit.json"
            input_path.write_text(json.dumps({"reviews": [ROW]}, ensure_ascii=False), encoding="utf-8")
            report = ext.run(str(input_path), apply=True, target=100, max_rows=1, audit_path=str(audit_path))
            self.assertTrue(audit_path.exists())
            self.assertEqual(report["before_assessed"], 26)
            self.assertEqual(report["after_assessed"], 27)
            self.assertTrue(report["zero_gemini_calls"])
            enrich.assert_called_once_with({})


if __name__ == "__main__":
    unittest.main()
