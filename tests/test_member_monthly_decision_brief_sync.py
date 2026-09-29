from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import member_monthly_decision_brief_sync as brief


def state(
    name,
    score,
    status="TEST",
    *,
    rank=None,
    classification="実務判断",
    confidence="高",
    readiness="高",
    current_month_change=False,
    delta=0,
):
    return {
        "page_id": ("a" * 31) + str((score or 0) % 10),
        "sync_id": f"id-{name}",
        "name": name,
        "status": status,
        "score": score,
        "judgment_reason": f"{name}の判断理由。",
        "plain_summary": f"{name}の概要。",
        "topic": f"{name}の最新変化。",
        "next_action": f"{name}を小さく検証する。",
        "main_risk": f"{name}の主リスク。",
        "best_for": f"{name}が向く用途。",
        "avoid_for": "",
        "confidence": confidence,
        "readiness": readiness,
        "category": "開発ツール",
        "classification": classification,
        "delta": delta,
        "change_reason": f"{name}の評価が変化した。",
        "important_at": "2026-09-20",
        "last_reviewed": "2026-09-28",
        "first_seen": "2026-09-01",
        "evidence": "https://example.com/evidence",
        "related_article": "",
        "primary_url": "https://example.com",
        "sources": ["OfficialVendor"],
        "rank": rank,
        "current_month_change": current_month_change,
    }


class MemberMonthlyDecisionBriefTests(unittest.TestCase):
    def test_top_prefers_existing_home_rank_then_score(self):
        rows = [
            state("Rank2", 82, rank=2),
            state("Rank1", 81, rank=1),
            state("HighScore", 99),
            state("Watch", 100, status="WATCH"),
            state("DeepTech", 100, classification="Deep Tech"),
        ]
        chosen = brief.select_top(rows, limit=3)
        self.assertEqual(["Rank1", "Rank2", "HighScore"], [x["name"] for x in chosen])

    def test_changes_require_current_month_and_meaningful_delta(self):
        rows = [
            state("BigUp", 80, current_month_change=True, delta=8),
            state("Tiny", 90, current_month_change=True, delta=2),
            state("Old", 99, current_month_change=False, delta=20),
            state("Down", 70, current_month_change=True, delta=-7),
        ]
        chosen = brief.select_changes(rows, limit=5)
        self.assertEqual(["BigUp", "Down"], [x["name"] for x in chosen])

    def test_build_blocks_refreshes_month_title_and_core_sections(self):
        now = datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)
        title, blocks, top_count, change_count = brief.build_blocks(
            [state("Tool", 88, rank=1, current_month_change=True, delta=6)],
            now=now,
        )
        self.assertEqual("会員限定Decision Brief｜2026年9月", title)
        self.assertEqual(1, top_count)
        self.assertEqual(1, change_count)
        rendered = str(blocks)
        self.assertIn("今月の結論", rendered)
        self.assertIn("今月、判断を変える必要があるもの", rendered)
        self.assertIn("最終自動更新：2026-09-29 JST", rendered)

    def test_sync_is_content_first_then_cleanup_then_title(self):
        calls = []
        old = [{"id": "old-1"}, {"id": "old-2"}]
        rows = [state("Tool", 88, rank=1)]

        def fake_append(page_id, blocks):
            calls.append(("append", page_id, len(blocks)))

        def fake_delete(block_id):
            calls.append(("delete", block_id))

        def fake_rename(page_id, title):
            calls.append(("rename", page_id, title))

        with patch.object(brief.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"), \
             patch.object(brief, "PAGE_ID", "page"), \
             patch.object(brief, "_query_states", return_value=rows), \
             patch.object(brief, "_children", return_value=old), \
             patch.object(brief, "_append", side_effect=fake_append), \
             patch.object(brief, "_delete", side_effect=fake_delete), \
             patch.object(brief, "_rename", side_effect=fake_rename):
            result = brief.sync_monthly_brief(
                now=datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)
            )

        self.assertEqual("append", calls[0][0])
        self.assertEqual(["delete", "delete"], [calls[1][0], calls[2][0]])
        self.assertEqual("rename", calls[3][0])
        self.assertTrue(result["zero_model_calls"])
        self.assertEqual(2, result["old_blocks_deleted"])

    def test_missing_page_id_fails_closed(self):
        with patch.object(brief.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "token"), \
             patch.object(brief, "PAGE_ID", ""):
            with self.assertRaisesRegex(ValueError, "MEMBER_MONTHLY_BRIEF_PAGE_ID"):
                brief.sync_monthly_brief()


if __name__ == "__main__":
    unittest.main()
