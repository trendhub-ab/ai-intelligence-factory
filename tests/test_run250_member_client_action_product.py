import unittest
from unittest.mock import patch

import member_client_action_alignment as alignment
import member_human_language_ux_v2 as ux2
import member_presentation_body_sync as body
import run250_member_client_action_product as run250


class Run250ClientActionProductTests(unittest.TestCase):
    def _state(self, name, category, score, text, *, status="TEST"):
        return {
            "sync_id": name,
            "name": name,
            "classification": "実務判断",
            "category": category,
            "status": status,
            "score": score,
            "confidence": "高",
            "readiness": "高",
            "plain_summary": text,
            "topic": text,
            "judgment_reason": "用途と運用条件を確認して判断する。",
            "best_for": text,
            "avoid_for": "条件が合わない用途には向かない。",
            "main_risk": "権限とデータ送信先を確認する必要がある。",
            "next_action": "自社案件に近い入力で小さく試し、費用と運用負荷を比較する。",
            "rank": None,
        }

    def test_icp_relevance_favors_client_work_over_deep_infra(self):
        client = self._state(
            "browser-agent",
            "エージェント",
            81,
            "顧客のブラウザ業務を自動化し、Webの定型ワークフローを小さく試す。",
        )
        infra = self._state(
            "inference-platform",
            "基盤",
            94,
            "KubernetesとGPUクラスタで分散推論するモデルサービング基盤。",
            status="ADOPT",
        )
        self.assertGreater(alignment.icp_relevance_score(client), alignment.icp_relevance_score(infra))
        self.assertGreater(alignment.product_rank_score(client), alignment.product_rank_score(infra))

    def test_deep_tech_inventory_is_not_deleted_or_reclassified(self):
        state = self._state("research", "基盤", 99, "Kubernetes推論基盤。")
        state["classification"] = "Deep Tech"
        before = dict(state)
        self.assertEqual(alignment.icp_relevance_score(state), 0.0)
        self.assertEqual(state, before)

    def test_navigation_proxy_never_changes_authoritative_scores(self):
        states = [
            self._state("client-tool", "製品・サービス", 82, "顧客FAQと業務自動化を小さく試せる。"),
            self._state("infra-tool", "基盤", 95, "Kubernetes GPUクラスタ向け推論サーバ。", status="ADOPT"),
        ]
        scores_before = {x["name"]: x["score"] for x in states}

        def score_ranker(rows, *, limit):
            ranked = sorted(rows, key=lambda x: float(x.get("score") or 0), reverse=True)[:limit]
            for index, row in enumerate(ranked, 1):
                row["rank"] = index
            return ranked

        selected = run250.rank_states_for_client_action(states, ranker=score_ranker, limit=1)
        self.assertEqual(selected[0]["name"], "client-tool")
        self.assertEqual({x["name"]: x["score"] for x in states}, scores_before)

    def test_run251_retires_pre_icp_fixed_editorial_shortlist(self):
        old = (
            "github:langgenius/dify",
            "github:mintplex-labs/anything-llm",
            "github:nvidia-nemo/guardrails",
        )
        original = ux2.EDITORIAL_HOME_SYNC_IDS
        try:
            ux2.EDITORIAL_HOME_SYNC_IDS = old
            retired = run250.retire_legacy_editorial_shortlist()
            self.assertEqual(retired, old)
            self.assertEqual(ux2.EDITORIAL_HOME_SYNC_IDS, ())
            # Evidence-reviewed copy remains available; only forced selection is retired.
            self.assertIn("github:nvidia-nemo/guardrails", ux2.EDITORIAL_COPY_OVERRIDES)
        finally:
            ux2.EDITORIAL_HOME_SYNC_IDS = original

    def test_action_layer_uses_existing_authoritative_fields(self):
        state = self._state(
            "client-tool",
            "製品・サービス",
            82,
            "顧客のFAQ案件で小さく試す。",
        )
        self.assertEqual(alignment.client_case_text(state), state["best_for"])
        self.assertIn(state["judgment_reason"], alignment.business_impact_text(state))
        self.assertIn(state["main_risk"], alignment.client_check_text(state))
        self.assertNotIn("自社", alignment.proposal_action_text(state))
        self.assertIn("対象案件", alignment.proposal_action_text(state))

    def test_decision_update_translates_direction_not_raw_score_only(self):
        state = self._state("tool", "製品・サービス", 80, "業務自動化ツール。")
        state["delta"] = -12
        state["change_reason"] = "公式が保守終了を明示したため。"
        text = alignment.decision_update_text(state)
        self.assertIn("慎重", text)
        self.assertIn("保守終了", text)
        self.assertNotIn("-12", text)

    def test_body_contract_is_client_action_first(self):
        state = self._state("tool", "製品・サービス", 82, "顧客FAQを小さく試す。")
        children = run250._build_children(state)
        headings = run250._heading_texts(children)
        self.assertIn("案件で使える場面", headings)
        self.assertIn("案件への意味（Business Impact）", headings)
        self.assertIn("提案前に確認すること", headings)
        self.assertIn("提案時の次の一手", headings)

    def test_old_member_body_cannot_false_match_new_product_contract(self):
        state = self._state("tool", "製品・サービス", 82, "顧客FAQを小さく試す。")
        old_children = [
            body._heading("これは何？"),
            body._heading("いま、どうする？"),
            body._heading("なぜ今見る？"),
            body._heading("次にやること"),
            body._heading("そう判断した理由"),
            body._heading("気をつけたいこと"),
        ]
        with patch.object(run250, "_BASE_BODY_MATCHES", lambda _children, _state: True):
            self.assertFalse(run250._body_matches_client_action(old_children, state))
            self.assertTrue(run250._body_matches_client_action(run250._build_children(state), state))

    def test_contract_declares_zero_provider_calls_and_schema_preservation(self):
        contract = run250.contract()
        self.assertTrue(contract["zero_gemini_calls"])
        self.assertTrue(contract["intelligence_engine_preserved"])
        self.assertTrue(contract["deep_tech_preserved"])
        self.assertTrue(contract["source_scores_preserved"])
        self.assertTrue(contract["evidence_preserved"])
        self.assertFalse(contract["notion_schema_changed"])
        self.assertTrue(contract["legacy_fixed_shortlist_retired"])
        self.assertTrue(contract["client_action_body_migration_required"])


if __name__ == "__main__":
    unittest.main()
