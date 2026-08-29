import unittest
from datetime import datetime, timezone

import member_presentation_sync as mps


class MemberCopySeparationTests(unittest.TestCase):
    def test_topic_removes_judgment_tail_and_duplicate(self):
        raw = (
            "高負荷LLMサービングではvLLMと並ぶ優先比較候補。"
            "判断点は、高負荷LLMサービングではvLLMと並ぶ優先比較候補。"
        )
        self.assertEqual(
            "高負荷LLMサービングではvLLMと並ぶ優先比較候補。",
            mps.clean_topic_trigger(raw),
        )

    def test_topic_drops_selected_action_sentence(self):
        action = "代表業務を1本実装し、既存Web基盤との親和性を確認する。"
        raw = "TypeScript組織ではテスト優先度が高い。" + action
        self.assertEqual(
            "TypeScript組織ではテスト優先度が高い。",
            mps.clean_topic_trigger(raw, action=action),
        )

    def test_generic_suffixes_are_removed(self):
        self.assertEqual(
            "権限設計が重要。",
            mps.clean_risk("権限設計が重要。" + mps.GENERIC_RISK_SUFFIX),
        )
        self.assertEqual(
            "TypeScriptチーム向け。",
            mps.clean_best_for("TypeScriptチーム向け。" + mps.GENERIC_BEST_SUFFIX),
        )
        self.assertEqual(
            "新規標準化には不向き。",
            mps.clean_avoid_for("新規標準化には不向き。" + mps.GENERIC_AVOID_SUFFIX),
        )

    def test_test_action_is_specific(self):
        rationale = (
            "TypeScript組織ではテスト優先度が高い。"
            "代表業務を1本実装し、既存Web基盤との親和性とロックイン範囲を確認する。"
            + mps.GENERIC_RATIONALE_SUFFIX
        )
        self.assertEqual(
            "代表業務を1本実装し、既存Web基盤との親和性とロックイン範囲を確認する。",
            mps.derive_next_action("TEST", rationale),
        )

    def test_declarative_candidate_falls_back_to_real_action(self):
        rationale = "エコシステムと一次情報の厚さから標準比較対象に置く価値が高い。"
        action = mps.derive_next_action("ADOPT", rationale)
        self.assertTrue(mps._is_action_sentence(action))
        self.assertIn("最終確認", action)

    def test_action_prefers_executable_second_sentence(self):
        rationale = (
            "高負荷LLMサービングではvLLMと並ぶ優先比較候補。"
            "自社モデル・GPU・同時接続条件で負荷試験し、総コストで選ぶ。"
        )
        self.assertEqual(
            "自社モデル・GPU・同時接続条件で負荷試験し、総コストで選ぶ。",
            mps.derive_next_action("ADOPT", rationale),
        )

    def test_avoid_action_never_uses_adoption_boilerplate(self):
        rationale = (
            "新規採用は見送り。"
            "現在保守されているコーディングエージェントへ比較対象を移す。"
            + mps.GENERIC_RATIONALE_SUFFIX
        )
        action = mps.derive_next_action("AVOID", rationale)
        self.assertIn("比較対象を移す", action)
        self.assertNotIn("採用時は", action)

    def test_duplicate_test_reason_uses_risk_based_causal_reason(self):
        topic = "TypeScript組織ではテスト優先度が高い。"
        reason = mps.derive_judgment_reason(
            "TEST",
            topic + "代表業務を1本実装して確認する。",
            topic,
            "固有APIへの依存範囲を確認する必要がある。",
            "代表業務を1本実装して確認する。",
        )
        self.assertNotEqual(mps._norm_key(topic), mps._norm_key(reason))
        self.assertIn("本番採用の前", reason)

    def test_change_reason_explains_direction_and_drops_action_tail(self):
        reason = (
            "リポジトリがArchivedになったため、以前のTEST評価を維持できない。"
            "判断点は、新規採用は見送り、代替候補へ移す。"
        )
        cleaned = mps.clean_change_reason(reason, -54)
        self.assertTrue(cleaned.startswith("前回より評価が下がったのは、"))
        self.assertIn("Archived", cleaned)
        self.assertNotIn("判断点は", cleaned)
        self.assertNotIn("代替候補へ移す", cleaned)

    def test_change_reason_drops_same_action_sentence(self):
        action = "代表業務を1本実装して確認する。"
        reason = "TypeScript組織ではテスト優先度が高い。" + action
        cleaned = mps.clean_change_reason(reason, 7, action=action)
        self.assertIn("TypeScript組織", cleaned)
        self.assertNotIn("代表業務", cleaned)

    def test_subthreshold_change_reason_stays_empty(self):
        self.assertEqual("", mps.clean_change_reason("少し変化", 3))


class HomepageRankingTests(unittest.TestCase):
    def _state(self, name, score, category, *, status="TEST", confidence="高", readiness="高"):
        return {
            "name": name,
            "score": score,
            "category": category,
            "status": status,
            "confidence": confidence,
            "readiness": readiness,
            "classification": "実務判断",
            "current_month_change": False,
            "delta": None,
            "rank": None,
        }

    def test_home_never_exceeds_eight(self):
        states = [self._state(f"tech-{i}", 100 - i, "開発ツール") for i in range(20)]
        selected = mps.assign_home_ranks(states, limit=8)
        self.assertEqual(8, len(selected))
        self.assertEqual(list(range(1, 9)), sorted(s["rank"] for s in selected))

    def test_diversity_does_not_push_materially_higher_score_below_lower_score(self):
        states = [
            self._state("A", 95, "開発ツール"),
            self._state("B", 94, "開発ツール"),
            self._state("C", 93, "セキュリティ"),
            self._state("D", 80, "AIモデル"),
        ]
        selected = mps.assign_home_ranks(states, limit=3)
        self.assertEqual(["A", "B", "C"], [s["name"] for s in selected])
        self.assertNotIn("D", [s["name"] for s in selected])

    def test_exact_tie_can_use_category_diversity(self):
        states = [
            self._state("A", 95, "開発ツール"),
            self._state("B", 94, "開発ツール"),
            self._state("C", 94, "セキュリティ"),
        ]
        selected = mps.assign_home_ranks(states, limit=3)
        self.assertEqual("A", selected[0]["name"])
        self.assertEqual("C", selected[1]["name"])
        self.assertEqual("B", selected[2]["name"])

    def test_watch_avoid_low_confidence_and_non_practical_are_excluded(self):
        states = [
            self._state("good", 90, "開発ツール"),
            self._state("watch", 99, "AIモデル", status="WATCH"),
            self._state("avoid", 99, "AIモデル", status="AVOID"),
            self._state("low", 99, "AIモデル", confidence="低"),
            {**self._state("deep", 99, "AIモデル"), "classification": "Deep Tech"},
        ]
        selected = mps.assign_home_ranks(states, limit=8)
        self.assertEqual(["good"], [s["name"] for s in selected])


class ChangeMonthTests(unittest.TestCase):
    def test_important_change_date_not_last_review_drives_month_flag(self):
        states = [
            {
                "important_at": "2026-08-10T00:00:00+00:00",
                "last_reviewed": "2026-09-01T00:00:00+00:00",
            }
        ]
        mps.mark_current_month_changes(
            states, now=datetime(2026, 8, 29, tzinfo=timezone.utc)
        )
        self.assertTrue(states[0]["current_month_change"])


class MappingTests(unittest.TestCase):
    def test_japanese_mappings_are_member_facing(self):
        self.assertEqual("高", mps.CONFIDENCE_JA["HIGH"])
        self.assertEqual("エージェント", mps.CATEGORY_JA["AGENT"])
        self.assertEqual("製品・サービス", mps.CATEGORY_JA["PRODUCT"])


if __name__ == "__main__":
    unittest.main()
