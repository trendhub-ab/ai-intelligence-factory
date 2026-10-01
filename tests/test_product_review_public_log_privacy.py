from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from unittest import mock

import pipeline


def test_product_review_runtime_redacts_paid_record_identity_from_persistence_logs(caplog):
    repo = {
        "nameWithOwner": "private-org/private-tool",
        "url": "https://example.invalid/private-tool",
        "source": "GitHub",
    }
    parsed = {
        "category": "DEVTOOLS",
        "adoption_score": 80,
        "adoption_status": "TEST",
        "evidence_confidence": "HIGH",
        "production_readiness": "HIGH",
        "main_risk_text": "risk",
        "best_for_text": "best",
        "avoid_for_text": "avoid",
        "short_rationale_text": "why",
        "source_summary_text": "summary",
    }
    source_info = {
        "verification_context": "verified",
        "context": "verified",
        "evidence_metadata": {},
        "primary_url": repo["url"],
    }
    resolution = SimpleNamespace(
        status="RESOLVED",
        entity_id="github:private-org/private-tool",
        primary_url=repo["url"],
        reason="",
    )

    caplog.set_level(logging.INFO, logger=pipeline.logger.name)
    with mock.patch.dict(os.environ, {"AIIF_PRODUCT_REVIEW_RUNTIME": "true"}, clear=False), \
         mock.patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
         mock.patch.object(pipeline, "validate_decision_intelligence_assessment", return_value=(True, [])), \
         mock.patch.object(pipeline.decision_intelligence, "resolve_canonical_entity_id", return_value=resolution), \
         mock.patch.object(pipeline, "_collect_final_evidence_urls", return_value=[]), \
         mock.patch.object(pipeline, "_notion_display_name", return_value="Private Tool"), \
         mock.patch.object(pipeline.decision_intelligence, "upsert_technology_intelligence", return_value={
             "saved": True,
             "page_id": "paid-page-id",
             "entity_id": resolution.entity_id,
             "created": False,
             "changed": True,
             "history_id": "history-id",
         }), \
         mock.patch.object(pipeline.evidence_ledger, "ENABLE_EVIDENCE_LEDGER", True), \
         mock.patch.object(pipeline, "_resolve_evidence_source_version", return_value=("", "")), \
         mock.patch.object(pipeline.evidence_ledger, "build_snapshots", return_value=[{"snapshot": 1}]), \
         mock.patch.object(pipeline.evidence_ledger, "persist_snapshots", return_value={"enabled": True, "saved": 1}):
        result = pipeline.persist_decision_intelligence_assessment(
            repo,
            parsed,
            source_info,
            {"state": "SUFFICIENT", "decision_scope_safe": True},
            "2026-10-02T00:00:00+00:00",
        )

    assert result["saved"] is True
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "private-org/private-tool" not in text
    assert "github:private-org/private-tool" not in text
    assert "paid-page-id" not in text
    assert "[EVIDENCE LEDGER]" in text
    assert "[DECISION INTELLIGENCE SAVED]" in text


def test_product_review_runtime_redacts_source_urls_and_usage_contexts():
    with mock.patch.dict(os.environ, {"AIIF_PRODUCT_REVIEW_RUNTIME": "true"}, clear=False):
        assert pipeline._public_log_value("https://private.example/source") == "<redacted>"

        audit = pipeline.GeminiUsageAudit()
        audit.record_attempt("gemini-3.6-flash", "product_review", "product_review:github:private-org/private-tool")
        audit.record_attempt("gemini-3.5-flash", "product_review", "product_review:arxiv:secret-record")
        summary = audit.summary(include_contexts=True)

    assert "private-org/private-tool" not in summary
    assert "secret-record" not in summary
    assert "product_review=2" in summary


def test_normal_runtime_keeps_non_product_log_values_unchanged():
    with mock.patch.dict(os.environ, {"AIIF_PRODUCT_REVIEW_RUNTIME": "false"}, clear=False):
        assert pipeline._public_log_value("https://public.example/source") == "https://public.example/source"
