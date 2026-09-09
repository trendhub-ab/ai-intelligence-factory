from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")

    def _network_forbidden(*args, **kwargs):
        raise AssertionError("Run307 unit tests must not perform network I/O")

    requests_stub.get = _network_forbidden
    requests_stub.post = _network_forbidden
    requests_stub.patch = _network_forbidden
    requests_stub.delete = _network_forbidden
    requests_stub.request = _network_forbidden
    requests_stub.Session = type("Session", (), {})
    requests_stub.Response = type("Response", (), {})
    sys.modules["requests"] = requests_stub

import member_presentation_body_sync as body
import run219_member_human_language_ui as run219
import run250_member_client_action_product as run250
import run270_proposal_first_member_surface as run270
import run307_use_decision_member_surface as run307


class Run307UseDecisionMemberSurfaceTests(unittest.TestCase):
    def _state(self, *, status="TEST", delta=None):
        return {
            "sync_id": "tool",
            "name": "Tool",
            "classification": "実務判断",
            "category": "開発ツール",
            "status": status,
            "score": 82,
            "confidence": "高",
            "readiness": "高",
            "plain_summary": "AIを組み込むための開発ツール。",
            "topic": "公式APIと運用条件が更新された。",
            "judgment_reason": "権限と費用を確認して判断する。",
            "best_for": "AI機能を組み込むWeb・業務システム。",
            "avoid_for": "外部送信できない環境。",
            "main_risk": "データ送信先と利用条件の確認が必要。",
            "next_action": "対象業務に近い入力で小さく試し、費用と運用負荷を比較する。",
            "change_reason": "公式が商用利用条件を更新したため。" if delta is not None else "",
            "delta": delta,
            "evidence": "https://example.com/docs",
            "primary_url": "https://example.com/docs",
            "related_article": "",
        }

    def test_contract_is_generic_and_supports_self_development(self):
        contract = run307.contract()
        self.assertEqual("use_decision_intelligence", contract["product_purpose"])
        self.assertTrue(contract["self_development_supported"])
        self.assertTrue(contract["internal_work_use_supported"])
        self.assertTrue(contract["client_proposal_supported"])
        self.assertFalse(contract["client_proposal_primary"])
        self.assertIn("個人事業主", contract["initial_icp"])
        self.assertIn("このAI、使える！", contract["primary_job"])
        self.assertIn("このAI、使える！", contract["core_promise"])
        self.assertTrue(contract["source_scores_preserved"])
        self.assertTrue(contract["decision_status_preserved"])
        self.assertTrue(contract["evidence_preserved"])
        self.assertFalse(contract["notion_schema_changed"])
        self.assertTrue(contract["zero_gemini_calls"])

    def test_body_is_use_decision_not_client_first(self):
        children = run307._build_children(self._state())
        headings = {text for _, text in body._body_fingerprint(children) if text}
        self.assertIn("いま、使える？", headings)
        self.assertIn("使える場面", headings)
        self.assertIn("使う前に確認すること", headings)
        self.assertIn("試す・導入する次の一手", headings)
        self.assertNotIn("顧客にどう答える？", headings)
        self.assertNotIn("提案できる場面", headings)
        self.assertNotIn("提案前に確認すること", headings)

    def test_body_uses_existing_authoritative_fields_without_mutation(self):
        state = self._state()
        before = dict(state)
        visible = " ".join(text for _, text in body._body_fingerprint(run307._build_children(state)))
        self.assertIn(state["best_for"], visible)
        self.assertIn(state["main_risk"], visible)
        self.assertIn(state["avoid_for"], visible)
        self.assertIn(state["next_action"], visible)
        self.assertEqual(before, state)

    def test_status_copy_is_generic(self):
        adopt = run307._use_decision_text(self._state(status="ADOPT"))
        test = run307._use_decision_text(self._state(status="TEST"))
        watch = run307._use_decision_text(self._state(status="WATCH"))
        avoid = run307._use_decision_text(self._state(status="AVOID"))
        for text in (adopt, test, watch, avoid):
            self.assertNotIn("顧客", text)
            self.assertNotIn("提案", text)
        self.assertIn("導入候補", adopt)
        self.assertIn("小さく検証", test)
        self.assertIn("採用を急がず", watch)
        self.assertIn("代替案", avoid)

    def test_decision_update_uses_usable_language_without_raw_delta(self):
        positive = run307._use_update_text(self._state(delta=12))
        negative = run307._use_update_text(self._state(delta=-12))
        self.assertIn("使える", positive)
        self.assertIn("材料が増え", positive)
        self.assertIn("利用判断", negative)
        self.assertIn("慎重", negative)
        self.assertNotIn("12", positive)
        self.assertNotIn("-12", negative)

    def test_proposal_first_body_cannot_false_match_current_contract(self):
        state = self._state()
        old = run270._build_children(state)
        current = run307._build_children(state)
        self.assertFalse(run307._body_matches_use_decision(old, state))
        self.assertTrue(run307._body_matches_use_decision(current, state))

    def test_installer_overrides_run270_on_active_wrapper_and_shared_body(self):
        fake_active = SimpleNamespace(_build_children=run270._build_children)
        original_builder = body._build_children
        original_matcher = body._body_matches
        try:
            run307.install_body(fake_active)
            self.assertIs(fake_active._build_children, run307._build_children)
            self.assertIs(body._build_children, run307._build_children)
            self.assertIs(body._body_matches, run307._body_matches_use_decision)
        finally:
            body._build_children = original_builder
            body._body_matches = original_matcher

    def test_run219_installs_run307_after_run270_and_reports_current_order(self):
        with (
            patch.object(run250, "install_body") as install250,
            patch.object(run270, "install_body") as install270,
            patch.object(run307, "install_body") as install307,
            patch.object(run219, "install") as install_run219,
            patch.object(run219.run215, "run_body_sync", return_value={}),
        ):
            result = run219.run_body_sync()
        install250.assert_called_once_with(sys.modules[run219.__name__])
        install270.assert_called_once_with(sys.modules[run219.__name__])
        install307.assert_called_once_with(sys.modules[run219.__name__])
        install_run219.assert_called_once_with()
        self.assertEqual(
            [
                "これは何？",
                "いま、使える？",
                "使える場面",
                "なぜ今見る？",
                "使う前に確認すること",
                "試す・導入する次の一手",
            ],
            result["reader_order"],
        )
        self.assertFalse(result["run307_use_decision_member_surface"]["client_proposal_primary"])

    def test_generated_callout_recognizer_accepts_current_shape(self):
        fake_block = {
            "type": "callout",
            "id": "block-1",
            "callout": {"rich_text": body._rich_text(run219.NEW_VISIBLE_CALLOUT_LABEL)},
        }
        current_children = [
            body._heading("いま、使える？"),
            body._heading("使える場面"),
            body._heading("試す・導入する次の一手"),
        ]
        self.assertTrue(
            run219._looks_like_generated_member_callout(
                fake_block,
                {"block-1": current_children},
            )
        )


if __name__ == "__main__":
    unittest.main()
