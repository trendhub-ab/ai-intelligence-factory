from datetime import datetime, timezone
import unittest

import member_monthly_decision_brief_sync as brief


class MemberMonthlyDecisionBriefHumanFourStepTests(unittest.TestCase):
    def test_top_item_uses_human_four_step_primary_reading_contract(self):
        record = {
            "page_id": "3d0479ff-dca9-8127-8b47-e0dccc7bb166",
            "sync_id": "id-tool",
            "name": "Tool",
            "status": "ADOPT",
            "score": 93,
            "judgment_reason": "採用判断の根拠。",
            "plain_summary": "複雑な処理をまとめて扱える基盤です。",
            "topic": "複数の処理を一つの流れで扱いやすくなります。",
            "next_action": "代表的な1処理を検証環境で動かす。",
            "main_risk": "運用前に権限設定を確認する必要があります。",
            "best_for": "AI・Web・業務システムを小さく試して導入判断するチーム。",
            "avoid_for": "",
            "confidence": "高",
            "readiness": "高",
            "category": "開発ツール",
            "classification": "実務判断",
            "delta": 0,
            "change_reason": "",
            "important_at": "2026-10-01",
            "last_reviewed": "2026-10-01",
            "first_seen": "2026-09-01",
            "evidence": "https://example.com/evidence",
            "related_article": "",
            "primary_url": "https://example.com",
            "sources": ["OfficialVendor"],
            "rank": 1,
            "current_month_change": False,
        }

        _, blocks, top_count, _ = brief.build_blocks(
            [record], now=datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(1, top_count)
        top_level = " ".join(
            str(block) for block in blocks if block.get("type") != "toggle"
        )
        labels = [
            "何が楽になる？：",
            "誰・どんな仕事向け？：",
            "まず何を試す？：",
            "注意点：",
        ]
        positions = [top_level.index(label) for label in labels]
        self.assertEqual(sorted(positions), positions)
        self.assertIn(record["topic"], top_level)
        self.assertIn(record["best_for"], top_level)
        self.assertIn("代表的な1処理を検証環境で動かす。", top_level)
        self.assertIn(record["main_risk"], top_level)
        self.assertNotIn("向いている場面：", top_level)
        self.assertNotIn("まずやること：", top_level)
        self.assertNotIn("今月のポイント：", top_level)

        toggles = " ".join(str(block) for block in blocks if block.get("type") == "toggle")
        self.assertIn("判断の理由：", toggles)
        self.assertIn("参考スコア：93点", toggles)
        self.assertNotIn(record["main_risk"], toggles)


if __name__ == "__main__":
    unittest.main()
