from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

# Repository-wide Falsification intentionally installs no Production dependencies.
# The Run270 presentation unit tests exercise deterministic rendering only, so provide
# a fail-closed requests stub before importing the member modules. Any accidental
# network use becomes an assertion instead of silently escaping the hermetic test.
if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")

    def _network_forbidden(*args, **kwargs):
        raise AssertionError("Run270 unit tests must not perform network I/O")

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


class Run270ProposalFirstMemberSurfaceTests(unittest.TestCase):
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
            "avoid_for": "外部送信できない案件。",
            "main_risk": "データ送信先と利用条件の確認が必要。",
            "next_action": "対象業務に近い入力で小さく試し、費用と運用負荷を比較する。",
            "change_reason": "公式が商用利用条件を更新したため。" if delta is not None else "",
            "delta": delta,
            "evidence": "https://example.com/docs",
            "primary_url": "https://example.com/docs",
            "related_article": "",
        }

    def test_contract_is_proposal_first_and_preserves_authority(self):
        contract = run270.contract()
        self.assertEqual("proposal_first_decision_intelligence", contract["product_purpose"])
        self.assertTrue(contract["client_proposal_primary"])
        self.assertTrue(contract["internal_work_use_secondary"])
        self.assertTrue(contract["skill_growth_secondary"])
        self.assertTrue(contract["source_scores_preserved"])
        self.assertTrue(contract["decision_status_preserved"])
        self.assertTrue(contract["evidence_preserved"])
        self.assertFalse(contract["notion_schema_changed"])
        self.assertTrue(contract["zero_gemini_calls"])
        self.assertIn("顧客", contract["initial_icp"])
        self.assertIn("提案", contract["primary_job"])

    def test_body_is_proposal_first_not_work_first(self):
        children = run270._build_children(self._state())
        headings = {text for _, text in body._body_fingerprint(children) if text}
        self.assertIn("顧客にどう答える？", headings)
        self.assertIn("提案できる場面", headings)
        self.assertIn("提案前に確認すること", headings)
        self.assertIn("提案・検証の次の一手", headings)
        self.assertNotIn("仕事で使える場面", headings)
        self.assertNotIn("仕事への意味（Business Impact）", headings)
        self.assertNotIn("試すときの次の一手", headings)

    def test_body_uses_existing_authoritative_fields_without_mutation(self):
        state = self._state()
        before = dict(state)
        visible = " ".join(text for _, text in body._body_fingerprint(run270._build_children(state)))
        self.assertIn(state["best_for"], visible)
        self.assertIn(state["main_risk"], visible)
        self.assertIn(state["avoid_for"], visible)
        self.assertIn(state["next_action"], visible)
        self.assertEqual(before, state)

    def test_decision_update_translates_direction_without_raw_delta(self):
        positive = run270._proposal_update_text(self._state(delta=12))
        negative = run270._proposal_update_text(self._state(delta=-12))
        self.assertIn("提案候補", positive)
        self.assertIn("再検討", positive)
        self.assertIn("提案判断", negative)
        self.assertIn("慎重", negative)
        self.assertNotIn("12", positive)
        self.assertNotIn("-12", negative)

    def test_work_first_body_cannot_false_match_proposal_first_contract(self):
        state = self._state()
        old = run250._build_children(state)
        current = run270._build_children(state)
        self.assertFalse(run270._body_matches_proposal_first(old, state))
        self.assertTrue(run270._body_matches_proposal_first(current, state))

    def test_installer_overrides_run250_on_active_wrapper_and_shared_body(self):
        fake_active = SimpleNamespace(_build_children=run250._build_children)
        original_builder = body._build_children
        original_matcher = body._body_matches
        try:
            run270.install_body(fake_active)
            self.assertIs(fake_active._build_children, run270._build_children)
            self.assertIs(body._build_children, run270._build_children)
            self.assertIs(body._body_matches, run270._body_matches_proposal_first)
        finally:
            body._build_children = original_builder
            body._body_matches = original_matcher

    def test_run219_installs_run270_after_run250_and_reports_proposal_order(self):
        with (
            patch.object(run250, "install_body") as install250,
            patch.object(run270, "install_body") as install270,
            patch.object(run219, "install") as install_run219,
            patch.object(run219.run215, "run_body_sync", return_value={}),
        ):
            result = run219.run_body_sync()
        install250.assert_called_once_with(sys.modules[run219.__name__])
        install270.assert_called_once_with(sys.modules[run219.__name__])
        install_run219.assert_called_once_with()
        self.assertEqual(
            [
                "これは何？",
                "顧客にどう答える？",
                "提案できる場面",
                "なぜ今見る？",
                "提案前に確認すること",
                "提案・検証の次の一手",
            ],
            result["reader_order"],
        )
        self.assertTrue(result["run270_proposal_first_member_surface"]["client_proposal_primary"])

    def test_generated_callout_recognizer_accepts_proposal_first_shape(self):
        fake_block = {
            "type": "callout",
            "id": "block-1",
            "callout": {"rich_text": body._rich_text(run219.NEW_VISIBLE_CALLOUT_LABEL)},
        }
        proposal_children = [
            body._heading("顧客にどう答える？"),
            body._heading("提案できる場面"),
            body._heading("提案・検証の次の一手"),
        ]
        self.assertTrue(
            run219._looks_like_generated_member_callout(
                fake_block,
                {"block-1": proposal_children},
            )
        )


if __name__ == "__main__":
    unittest.main()
