import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import context_first_enrichment as cfe
import daily_portfolio_review as daily


def _rich(text):
    return {"type": "rich_text", "rich_text": ([{"plain_text": text, "text": {"content": text}}] if text else [])}


def _title(text):
    return {"type": "title", "title": [{"plain_text": text, "text": {"content": text}}]}


def _select(value):
    return {"type": "select", "select": ({"name": value} if value else None)}


def _date(value):
    return {"type": "date", "date": ({"start": value} if value else None)}


def _internal_page(
    *,
    entity_id="tech-1",
    name="MLflow",
    display="MLflow — AI・機械学習の実験やモデルを管理するMLOps基盤",
    plain="",
    topic="",
    category="DEVTOOLS",
    rationale="LLMやAIエージェントのトレーシング、評価、プロンプト管理まで用途が広がっている。",
    screening="",
    reviewed="2026-08-29T00:00:00+00:00",
    assessment="ASSESSED",
    tracking=True,
    tracking_status="ACTIVE",
):
    di = cfe.decision_intelligence
    return {
        "id": "internal-page-1",
        "properties": {
            di.TECH_PROP_NAME: _title(name),
            di.TECH_PROP_JAPANESE_DISPLAY_LABEL: _rich(display),
            cfe.TECH_PROP_PLAIN_SUMMARY: _rich(plain),
            cfe.TECH_PROP_TOPIC_TRIGGER: _rich(topic),
            di.TECH_PROP_CATEGORY: _select(category),
            di.TECH_PROP_SHORT_RATIONALE: _rich(rationale),
            di.TECH_PROP_SCREENING_REASON: _rich(screening),
            di.TECH_PROP_ENTITY_ID: _rich(entity_id),
            di.TECH_PROP_ASSESSMENT_STATE: _select(assessment),
            di.TECH_PROP_TRACKING_STATUS: _select(tracking_status),
            di.TECH_PROP_TRACKING_ELIGIBILITY: {"type": "checkbox", "checkbox": tracking},
            di.TECH_PROP_LAST_REVIEWED: _date(reviewed),
        },
    }


def _subscriber_page(*, entity_id="tech-1", plain="", topic=""):
    di = cfe.decision_intelligence
    return {
        "id": "subscriber-page-1",
        "properties": {
            di.SUB_PROP_ENTITY_ID: _rich(entity_id),
            cfe.SUB_PROP_PLAIN_SUMMARY: _rich(plain),
            cfe.SUB_PROP_TOPIC_TRIGGER: _rich(topic),
        },
    }


class ContextFirstDerivationTests(unittest.TestCase):
    def test_plain_summary_prefers_existing_copy(self):
        state = {
            "plain_summary": "人間が確認した説明です。",
            "technology_name": "MLflow",
            "japanese_display_label": "MLflow — 別の説明",
            "category": "DEVTOOLS",
        }
        self.assertEqual(cfe.derive_plain_summary(state), "人間が確認した説明です。")

    def test_plain_summary_extracts_existing_product_review_display_label(self):
        result = cfe.derive_plain_summary({
            "technology_name": "MLflow",
            "japanese_display_label": "MLflow — AI・機械学習の実験やモデルを管理するMLOps基盤",
            "category": "DEVTOOLS",
        })
        self.assertEqual(result, "AI・機械学習の実験やモデルを管理するMLOps基盤。")

    def test_plain_summary_has_safe_non_engineer_fallback(self):
        result = cfe.derive_plain_summary({
            "technology_name": "Example Agent",
            "japanese_display_label": "",
            "category": "AGENT",
        })
        self.assertIn("AIエージェント", result)
        self.assertNotIn("導入すべき", result)
        self.assertTrue(result.endswith("。"))

    def test_topic_trigger_does_not_invent_breaking_news(self):
        result = cfe.derive_topic_trigger({
            "technology_name": "MLflow",
            "short_rationale": "LLMのトレーシングと評価にも用途が広がっている",
        })
        self.assertTrue(result.startswith("今回の確認では、"))
        self.assertNotIn("最新ニュース", result)
        self.assertNotIn("新発表", result)
        self.assertNotIn("リリースされた", result)

    def test_context_module_has_no_provider_generation_call_site(self):
        source = Path(cfe.__file__).read_text(encoding="utf-8")
        for forbidden in ("import google", "from google", "generate_content(", "_generate_with"):
            self.assertNotIn(forbidden, source)


class ContextFirstSyncTests(unittest.TestCase):
    def _common_patches(self, internal, subscriber):
        return (
            patch.object(cfe.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True),
            patch.object(cfe.decision_intelligence, "ENABLE_SUBSCRIBER_TECH_SYNC", True),
            patch.object(cfe.decision_intelligence, "query_technology_records", return_value=[internal]),
            patch.object(cfe.decision_intelligence, "sync_subscriber_technology_db", return_value={"enabled": True, "unchanged": 1}),
            patch.object(cfe.decision_intelligence, "_query_external_db", return_value=[subscriber]),
            patch.object(cfe, "_patch_context"),
        )

    def test_existing_member_copy_is_preserved_when_not_reviewed(self):
        internal = _internal_page(
            plain="内部の説明。",
            topic="内部の前回話題。",
            reviewed="2026-08-28T00:00:00+00:00",
        )
        subscriber = _subscriber_page(
            plain="会員向けに手で磨いた説明。",
            topic="会員向けに手で磨いた話題。",
        )
        p1, p2, p3, p4, p5, p6 = self._common_patches(internal, subscriber)
        with p1, p2, p3, p4, p5, p6 as patch_context:
            result = cfe.enrich_context_first({"tech-1": "2026-08-28T00:00:00+00:00"})

        patch_context.assert_not_called()
        self.assertEqual(result["subscriber_preserved"], 1)
        self.assertTrue(result["zero_gemini_calls"])

    def test_missing_review_snapshot_defaults_to_preserve_not_refresh(self):
        internal = _internal_page(
            plain="内部の説明。",
            topic="内部の前回話題。",
            reviewed="2026-08-29T00:00:00+00:00",
        )
        subscriber = _subscriber_page(
            plain="会員向けに手で磨いた説明。",
            topic="会員向けに手で磨いた話題。",
        )
        p1, p2, p3, p4, p5, p6 = self._common_patches(internal, subscriber)
        with p1, p2, p3, p4, p5, p6 as patch_context:
            result = cfe.enrich_context_first(None)

        patch_context.assert_not_called()
        self.assertEqual(result["subscriber_preserved"], 1)

    def test_review_refreshes_topic_but_never_overwrites_member_plain_summary(self):
        internal = _internal_page(
            plain="内部の説明。",
            topic="古い話題。",
            reviewed="2026-08-29T00:00:00+00:00",
            rationale="AIエージェントの評価機能が現在の判断材料になっている。",
        )
        subscriber = _subscriber_page(
            plain="会員向けに手で磨いた説明。",
            topic="古い会員向け話題。",
        )
        p1, p2, p3, p4, p5, p6 = self._common_patches(internal, subscriber)
        with p1, p2, p3, p4, p5, p6 as patch_context:
            result = cfe.enrich_context_first({"tech-1": "2026-08-28T00:00:00+00:00"})

        self.assertEqual(patch_context.call_count, 2)
        internal_props = patch_context.call_args_list[0].args[1]
        subscriber_props = patch_context.call_args_list[1].args[1]
        self.assertIn(cfe.TECH_PROP_TOPIC_TRIGGER, internal_props)
        self.assertNotIn(cfe.TECH_PROP_PLAIN_SUMMARY, internal_props)
        self.assertIn(cfe.SUB_PROP_TOPIC_TRIGGER, subscriber_props)
        self.assertNotIn(cfe.SUB_PROP_PLAIN_SUMMARY, subscriber_props)
        self.assertEqual(result["subscriber_updated"], 1)

    def test_blank_internal_context_is_never_sent_to_subscriber(self):
        internal = _internal_page(plain="", topic="")
        subscriber = _subscriber_page(plain="既存説明。", topic="既存話題。")
        p1, p2, p3, p4, p5, p6 = self._common_patches(internal, subscriber)
        with p1, p2, p3, p4, p5, p6 as patch_context, \
             patch.object(cfe, "derive_plain_summary", return_value=""), \
             patch.object(cfe, "derive_topic_trigger", return_value=""):
            cfe.enrich_context_first({"tech-1": "2026-08-28T00:00:00+00:00"})

        patch_context.assert_not_called()

    def test_preflight_fails_closed_when_required_context_property_is_missing(self):
        with patch.object(cfe.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(cfe.decision_intelligence, "ENABLE_SUBSCRIBER_TECH_SYNC", False), \
             patch.object(cfe, "_schema_properties", return_value={
                 cfe.TECH_PROP_PLAIN_SUMMARY: {"type": "rich_text"},
             }):
            with self.assertRaisesRegex(ValueError, "Topic Trigger"):
                cfe.preflight_context_first_schema()


class DailyRun132IntegrationTests(unittest.TestCase):
    def test_context_enrichment_runs_even_when_product_review_budget_is_zero(self):
        state = {"canonical_entity_id": "tech-1", "last_reviewed": "2026-08-28T00:00:00+00:00"}
        output = io.StringIO()
        with patch.object(daily.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(daily, "DEFAULT_MAX_REVIEWS", 0), \
             patch.object(daily, "DEFAULT_REQUEST_BUDGET", 0), \
             patch.object(daily.decision_intelligence, "query_technology_records", return_value=[{"id": "p1"}]), \
             patch.object(daily.decision_intelligence, "technology_page_to_state", return_value=state), \
             patch.object(daily, "plan_daily_review_allowlist", return_value=[]), \
             patch.object(daily.context_first_enrichment, "preflight_context_first_schema") as preflight, \
             patch.object(daily.context_first_enrichment, "enrich_context_first", return_value={"enabled": True, "zero_gemini_calls": True}) as enrich, \
             redirect_stdout(output):
            rc = daily.main()

        self.assertEqual(rc, 0)
        preflight.assert_called_once_with()
        enrich.assert_called_once_with({"tech-1": "2026-08-28T00:00:00+00:00"})
        self.assertIn('"zero_gemini_calls": true', output.getvalue())


if __name__ == "__main__":
    unittest.main()
