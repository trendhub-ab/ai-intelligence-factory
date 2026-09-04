import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import run225_stock_lifecycle as lifecycle
import stock_lifecycle_reconcile as reconcile


NOW = datetime(2026, 9, 4, 7, 0, tzinfo=timezone.utc)


def iso_days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


class LifecycleBoundaryTests(unittest.TestCase):
    def test_fresh_boundary_includes_30_days(self):
        self.assertEqual(
            lifecycle.FRESH,
            lifecycle.classify_lifecycle(source="HackerNews", published_at=iso_days_ago(30), now=NOW).label,
        )

    def test_aging_starts_at_31_days(self):
        self.assertEqual(
            lifecycle.AGING,
            lifecycle.classify_lifecycle(source="HackerNews", published_at=iso_days_ago(31), now=NOW).label,
        )

    def test_aging_includes_90_days(self):
        self.assertEqual(
            lifecycle.AGING,
            lifecycle.classify_lifecycle(source="ProductHunt", published_at=iso_days_ago(90), now=NOW).label,
        )

    def test_old_discovery_news_archives_at_91_days(self):
        decision = lifecycle.classify_lifecycle(
            source="HackerNews", published_at=iso_days_ago(91), name="Model launch", now=NOW
        )
        self.assertEqual(lifecycle.ARCHIVE, decision.label)
        self.assertFalse(decision.active)

    def test_old_github_asset_becomes_evergreen(self):
        decision = lifecycle.classify_lifecycle(
            source="GitHub", published_at=iso_days_ago(180), name="vllm-project/vllm", now=NOW
        )
        self.assertEqual(lifecycle.EVERGREEN, decision.label)
        self.assertTrue(decision.active)

    def test_old_arxiv_asset_becomes_evergreen(self):
        decision = lifecycle.classify_lifecycle(
            source="ArXiv", published_at=iso_days_ago(365), name="Coordination in Multi-Agent AI", now=NOW
        )
        self.assertEqual(lifecycle.EVERGREEN, decision.label)

    def test_durable_source_with_explicit_event_signal_archives(self):
        decision = lifecycle.classify_lifecycle(
            source="GitHub",
            published_at=iso_days_ago(120),
            name="Security incident postmortem",
            now=NOW,
        )
        self.assertEqual(lifecycle.ARCHIVE, decision.label)

    def test_missing_date_is_fail_safe_aging_not_fresh(self):
        decision = lifecycle.classify_lifecycle(source="GitHub", now=NOW)
        self.assertEqual(lifecycle.AGING, decision.label)
        self.assertIsNone(decision.age_days)

    def test_recent_review_repromotes_old_asset(self):
        decision = lifecycle.classify_lifecycle(
            source="HackerNews",
            published_at=iso_days_ago(180),
            reviewed_at=iso_days_ago(2),
            now=NOW,
        )
        self.assertEqual(lifecycle.FRESH, decision.label)
        self.assertEqual("reviewed_at", decision.anchor)

    def test_future_timestamp_is_clamped_to_fresh(self):
        decision = lifecycle.classify_lifecycle(
            source="ProductHunt", published_at=(NOW + timedelta(days=2)).isoformat(), now=NOW
        )
        self.assertEqual(lifecycle.FRESH, decision.label)
        self.assertEqual(0, decision.age_days)


class RecordAdapterTests(unittest.TestCase):
    def test_active_for_review_excludes_only_archive(self):
        old_news = SimpleNamespace(
            source=("HackerNews",),
            published_at=iso_days_ago(120),
            analyzed_at=None,
            last_reviewed=None,
            name="Acquisition announcement",
            source_summary="",
        )
        old_repo = SimpleNamespace(
            source=("GitHub",),
            published_at=iso_days_ago(120),
            analyzed_at=None,
            last_reviewed=None,
            name="project/repo",
            source_summary="runtime library",
        )
        self.assertFalse(lifecycle.active_for_review(old_news, now=NOW))
        self.assertTrue(lifecycle.active_for_review(old_repo, now=NOW))


class ReconcileSafetyTests(unittest.TestCase):
    @staticmethod
    def _page(page_id: str, name: str, source: str, days: int, current: str = ""):
        def text_prop(value: str, kind: str):
            return {kind: [{"plain_text": value}]}

        return {
            "id": page_id,
            "properties": {
                "記事名": text_prop(name, "title"),
                "評価状態": {"select": {"name": "Stocked"}},
                "情報源": {"select": {"name": source}},
                "公開日": {"date": {"start": iso_days_ago(days)}},
                "分析日": {"date": {"start": iso_days_ago(days)}},
                "元情報要約": text_prop("summary", "rich_text"),
                "更新状態": {"select": ({"name": current} if current else None)},
            },
        }

    def test_fresh_blank_encoding_requires_no_write(self):
        page = self._page("fresh", "fresh item", "HackerNews", 2, "")
        with patch.object(reconcile, "query_stocked_pages", return_value=[page]), patch.object(
            reconcile, "_patch_lifecycle"
        ) as writer:
            result = reconcile.reconcile(apply=True, now=NOW)
        self.assertEqual(0, result["changes_needed"])
        writer.assert_not_called()

    def test_only_lifecycle_property_is_written_for_aging(self):
        page = self._page("aging", "aging item", "HackerNews", 45, "")
        with patch.object(reconcile, "query_stocked_pages", return_value=[page]), patch.object(
            reconcile, "_patch_lifecycle"
        ) as writer:
            result = reconcile.reconcile(apply=True, now=NOW)
        self.assertEqual(1, result["updated"])
        writer.assert_called_once_with("aging", lifecycle.AGING)
        self.assertEqual(0, result["destructive_deletes"])
        self.assertTrue(result["zero_gemini_calls"])

    def test_repromotion_to_fresh_clears_materialized_state(self):
        page = self._page("repromote", "reviewed item", "HackerNews", 2, lifecycle.ARCHIVE)
        with patch.object(reconcile, "query_stocked_pages", return_value=[page]), patch.object(
            reconcile, "_patch_lifecycle"
        ) as writer:
            result = reconcile.reconcile(apply=True, now=NOW)
        self.assertEqual(1, result["updated"])
        writer.assert_called_once_with("repromote", "")


if __name__ == "__main__":
    unittest.main()
