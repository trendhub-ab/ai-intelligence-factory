import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import member_client_action_alignment as alignment
import member_human_language_ux_v2 as ux2
import member_presentation_body_sync as body
import run219_member_human_language_ui as run219
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

    def test_run254_icp_is_work_first_without_redundant_first_person(self):
        self.assertIn("AIを仕事に活用", alignment.ICP_LABEL)
        self.assertIn("ツールを選び", alignment.ICP_LABEL)
        self.assertNotIn("自分の", alignment.ICP_LABEL)
        self.assertNotIn("顧客からAI活用を相談", alignment.ICP_LABEL)

    def test_icp_relevance_favors_direct_work_use_over_deep_infra(self):
        work_tool = self._state(
            "browser-agent",
            "エージェント",
            81,
            "ブラウザの定型作業を自動化し、日々のワークフローを小さく試す。",
        )
        infra = self._state(
            "inference-platform",
            "基盤",
            94,
            "KubernetesとGPUクラスタで分散推論するモデルサービング基盤。",
            status="ADOPT",
        )
        self.assertGreater(alignment.icp_relevance_score(work_tool), alignment.icp_relevance_score(infra))
        self.assertGreater(alignment.product_rank_score(work_tool), alignment.product_rank_score(infra))

    def test_client_terms_are_secondary_not_required_for_relevance(self):
        work_text = "画像と動画の制作作業を再利用できるワークフローにして効率化する。"
        work_tool = self._state("creative-tool", "マルチモーダル", 82, work_text)
        self.assertNotIn("顧客", work_text)
        self.assertGreaterEqual(alignment.icp_relevance_score(work_tool), 80.0)

    def test_deep_tech_inventory_is_not_deleted_or_reclassified(self):
        state = self._state("research", "基盤", 99, "Kubernetes推論基盤。")
        state["classification"] = "Deep Tech"
        before = dict(state)
        self.assertEqual(alignment.icp_relevance_score(state), 0.0)
        self.assertEqual(state, before)

    def test_navigation_proxy_never_changes_authoritative_scores(self):
        states = [
            self._state("work-tool", "製品・サービス", 82, "FAQと業務自動化を小さく試せる。"),
            self._state("infra-tool", "基盤", 95, "Kubernetes GPUクラスタ向け推論サーバ。", status="ADOPT"),
        ]
        scores_before = {x["name"]: x["score"] for x in states}

        def score_ranker(rows, *, limit):
            ranked = sorted(rows, key=lambda x: float(x.get("score") or 0), reverse=True)[:limit]
            for index, row in enumerate(ranked, 1):
                row["rank"] = index
            return ranked

        selected = run250.rank_states_for_client_action(states, ranker=score_ranker, limit=1)
        self.assertEqual(selected[0]["name"], "work-tool")
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
            self.assertIn("github:nvidia-nemo/guardrails", ux2.EDITORIAL_COPY_OVERRIDES)
        finally:
            ux2.EDITORIAL_HOME_SYNC_IDS = original

    def test_neutral_subject_text_removes_only_redundant_product_phrasing(self):
        self.assertEqual(alignment.neutral_subject_text("自分の仕事に使う"), "仕事に使う")
        self.assertEqual(alignment.neutral_subject_text("自分の利用条件を確認"), "利用条件を確認")
        self.assertEqual(alignment.neutral_subject_text("自分だけで使う"), "自分だけで使う")

    def test_work_action_layer_uses_existing_authoritative_fields(self):
        state = self._state(
            "work-tool",
            "製品・サービス",
            82,
            "FAQ業務で小さく試す。",
        )
        self.assertEqual(alignment.work_case_text(state), state["best_for"])
        self.assertIn(state["judgment_reason"], alignment.business_impact_text(state))
        self.assertIn(state["main_risk"], alignment.work_check_text(state))
        self.assertIn("向かない条件：", alignment.work_check_text(state))
        self.assertNotIn("自社", alignment.work_action_text(state))
        self.assertNotIn("自分の", alignment.work_action_text(state))
        self.assertIn("対象業務", alignment.work_action_text(state))
        # Legacy callable names remain aliases only for compatibility.
        self.assertEqual(alignment.client_case_text(state), alignment.work_case_text(state))
        self.assertEqual(alignment.client_check_text(state), alignment.work_check_text(state))
        self.assertEqual(alignment.proposal_action_text(state), alignment.work_action_text(state))

    def test_decision_update_translates_direction_not_raw_score_only(self):
        state = self._state("tool", "製品・サービス", 80, "業務自動化ツール。")
        state["delta"] = -12
        state["change_reason"] = "公式が保守終了を明示したため。"
        text = alignment.decision_update_text(state)
        self.assertIn("仕事で使う候補", text)
        self.assertIn("慎重", text)
        self.assertIn("保守終了", text)
        self.assertNotIn("-12", text)

    def test_body_contract_is_work_first(self):
        state = self._state("tool", "製品・サービス", 82, "FAQ業務を小さく試す。")
        children = run250._build_children(state)
        headings = run250._heading_texts(children)
        self.assertIn("仕事で使える場面", headings)
        self.assertIn("仕事への意味（Business Impact）", headings)
        self.assertIn("使う前に確認すること", headings)
        self.assertIn("試すときの次の一手", headings)
        self.assertNotIn("案件で使える場面", headings)
        self.assertNotIn("提案時の次の一手", headings)

    def test_old_client_action_body_cannot_false_match_work_first_contract(self):
        state = self._state("tool", "製品・サービス", 82, "FAQ業務を小さく試す。")
        old_client_children = [
            body._heading("これは何？"),
            body._heading("いま、どうする？"),
            body._heading("案件で使える場面"),
            body._heading("案件への意味（Business Impact）"),
            body._heading("提案前に確認すること"),
            body._heading("提案時の次の一手"),
        ]
        with patch.object(run250, "_BASE_BODY_MATCHES", lambda _children, _state: True):
            self.assertFalse(run250._body_matches_client_action(old_client_children, state))
            self.assertTrue(run250._body_matches_client_action(run250._build_children(state), state))

    def test_run254_rewrites_work_first_body_with_redundant_first_person(self):
        state = self._state("tool", "製品・サービス", 82, "FAQ業務を小さく試す。")
        stale = run250._build_children(state)
        stale.append(body._paragraph("自分の仕事に使える候補です。"))
        with patch.object(run250, "_BASE_BODY_MATCHES", lambda _children, _state: True):
            self.assertFalse(run250._body_matches_client_action(stale, state))
            fresh = run250._build_children({**state, "topic": "自分の仕事で確認する。"})
            self.assertTrue(run250._body_matches_client_action(fresh, state))
            self.assertNotIn("自分の仕事", run250._visible_text(fresh))

    def test_run252_installer_binds_active_wrapper_even_after_shared_install(self):
        fake_active = SimpleNamespace(_build_children=lambda _state: [])
        original_body_builder = body._build_children
        try:
            with patch.object(run250, "_BODY_INSTALLED", True):
                run250.install_body(fake_active)
            self.assertIs(fake_active._build_children, run250._build_children)
            self.assertIs(body._build_children, run250._build_children)
        finally:
            body._build_children = original_body_builder

    def test_run219_passes_current_module_object_and_reports_work_first_order(self):
        with (
            patch.object(run250, "install_body") as install_body,
            patch.object(run219, "install") as install_run219,
            patch.object(run219.run215, "run_body_sync", return_value={}),
        ):
            result = run219.run_body_sync()
        install_body.assert_called_once_with(sys.modules[run219.__name__])
        install_run219.assert_called_once_with()
        self.assertTrue(result["run250_client_action_product"]["script_entrypoint_body_authority"])
        self.assertEqual(
            result["reader_order"][:6],
            [
                "これは何？",
                "いま、どうする？",
                "仕事で使える場面",
                "仕事への意味（Business Impact）",
                "使う前に確認すること",
                "試すときの次の一手",
            ],
        )

    def test_contract_declares_work_first_neutral_subject_and_preserves_authority(self):
        contract = run250.contract()
        self.assertEqual(contract["product_purpose"], "work_first_decision_intelligence")
        self.assertEqual(contract["subject_style"], "implicit_neutral_subject")
        self.assertTrue(contract["client_proposal_secondary"])
        self.assertTrue(contract["zero_gemini_calls"])
        self.assertTrue(contract["intelligence_engine_preserved"])
        self.assertTrue(contract["deep_tech_preserved"])
        self.assertTrue(contract["source_scores_preserved"])
        self.assertTrue(contract["evidence_preserved"])
        self.assertFalse(contract["notion_schema_changed"])
        self.assertTrue(contract["legacy_fixed_shortlist_retired"])
        self.assertTrue(contract["work_first_body_migration_required"])
        self.assertTrue(contract["neutral_subject_body_migration_required"])
        self.assertTrue(contract["script_entrypoint_body_authority"])


if __name__ == "__main__":
    unittest.main()
