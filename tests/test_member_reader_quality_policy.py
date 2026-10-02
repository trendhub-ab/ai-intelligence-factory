from __future__ import annotations

from datetime import date
import unittest

import member_reader_quality_policy as policy


class MemberReaderQualityPolicyTests(unittest.TestCase):
    TODAY = date(2026, 10, 1)

    def test_recorded_dates_are_shared_and_not_page_update_dates(self):
        for raw in ("2026-09-30", "2026-09-30T03:00:00Z"):
            self.assertEqual("recorded", policy.review_state(raw, as_of=self.TODAY))
            self.assertEqual("2026年9月30日", policy.review_badge(raw, as_of=self.TODAY))
            self.assertIn("2026年9月30日に確認", policy.review_disclosure(raw, as_of=self.TODAY))
        self.assertNotIn("2026年10月1日に確認",
                         policy.review_disclosure("2026-09-30", as_of=self.TODAY))

    def test_thirty_day_cutoff_and_future_dates_are_honest(self):
        self.assertEqual("recorded", policy.review_state("2026-09-01", as_of=self.TODAY))
        self.assertEqual("older", policy.review_state("2026-08-31", as_of=self.TODAY))
        self.assertIn("30日超", policy.review_badge("2026-08-31", as_of=self.TODAY))
        self.assertIn("30日を超えています",
                      policy.review_disclosure("2026-08-31", as_of=self.TODAY))
        self.assertEqual("future", policy.review_state("2026-10-02", as_of=self.TODAY))
        self.assertEqual("確認日を要確認",
                         policy.review_badge("2026-10-02", as_of=self.TODAY))
        self.assertNotIn("2026年10月2日に確認",
                         policy.review_disclosure("2026-10-02", as_of=self.TODAY))

    def test_missing_and_invalid_date_never_claim_verified_evidence(self):
        self.assertEqual("missing", policy.review_state(None, as_of=self.TODAY))
        self.assertEqual("未記録", policy.review_badge("", as_of=self.TODAY))
        self.assertIn("最終確認日が記録されていません",
                      policy.review_disclosure(None, as_of=self.TODAY))
        for bad in ("2026-99-33", "2026-10-01fake", "not-a-date"):
            self.assertEqual("invalid", policy.review_state(bad, as_of=self.TODAY))
            self.assertIn("不整合", policy.review_disclosure(bad, as_of=self.TODAY))
            self.assertEqual("", policy.display_date(bad))

    def test_long_generated_action_quotes_do_not_repeat_the_use_case(self):
        use = "順次・並列・DAG等の柔軟なトポロジやMCP統合を必要とする複雑なマルチエージェント連携システムの開発"
        tail = "代表タスクを20件程度用意し、小規模テストで品質・速度・費用を現行候補と比較する。"
        state = {"best_for": use, "next_action": f"「{use}」を想定し、{tail}"}
        self.assertEqual(tail, policy.reader_action(state))
        self.assertIn(use, state["next_action"])

    def test_long_deep_tech_action_retains_the_recheck_instructions(self):
        use = "公開実装を再現し、複数の評価データを同じ条件で比較して研究の妥当性を確かめたい研究開発チーム"
        tail = "次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。"
        state = {"best_for": use, "next_action": f"「{use}」を想定し、{tail}"}
        self.assertEqual(tail, policy.reader_action(state))

    def test_topic_quote_and_custom_actions_are_not_blindly_cut(self):
        focus = "テキストだけでなく画像・音声・動画なども扱い、巨大データをストリーミング処理できる標準的なデータ基盤として成熟しています"
        tail = "代表的な1つの処理を検証環境で動かし、現在の方法と速度・費用・運用負荷を比較する。"
        state = {"topic": focus, "next_action": f"今回の論点「{focus}」を踏まえ、{tail}"}
        self.assertEqual(tail, policy.reader_action(state))
        custom = f"「{focus}」を想定し、必ず権限の上限を設定する。"
        self.assertEqual(custom, policy.reader_action({**state, "next_action": custom}))
        self.assertEqual(state["next_action"], policy.reader_action({**state, "topic": "別の話題"}))

    def test_risk_is_not_repeated_in_reason_but_unique_reason_survives(self):
        risk = "ループが止まらず、API費用が増えるリスクがあります。"
        state = {"main_risk": risk, "judgment_reason": risk + "そのため、本番導入の前に小さく試して確認します。"}
        self.assertEqual("", policy.reader_reason(state))
        state["judgment_reason"] = "複数のAIを連携できます。" + risk
        self.assertEqual("複数のAIを連携できます。", policy.reader_reason(state))
        self.assertEqual(risk, state["main_risk"])

    def test_reason_prefix_matching_does_not_remove_a_qualifier(self):
        state = {"main_risk": "費用", "judgment_reason": "費用を抑えやすいことが判断の理由です。"}
        self.assertEqual(state["judgment_reason"], policy.reader_reason(state))

    def test_status_and_source_links_cannot_claim_unverified_origin(self):
        self.assertIn("使う候補", policy.LONG_STATUS["ADOPT"])
        self.assertIn("小さく試す", policy.status_short("TEST"))
        self.assertNotEqual("ADOPT", policy.status_short("ADOPT"))
        self.assertEqual("参照先 1：comet.com",
                         policy.source_link_label("https://www.comet.com/docs/x"))
        self.assertEqual("参照先 1",
                         policy.source_link_label("http://example.com/unverified"))


if __name__ == "__main__":
    unittest.main()
