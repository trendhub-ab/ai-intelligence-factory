import os
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run173_operational_yield as run173


class TransportTimeout(TimeoutError):
    pass


def fake_pipeline(generate=None, rescue=None):
    ns = types.SimpleNamespace()
    ns.SESSION_UNAVAILABLE_MODELS = set()
    ns.logger = MagicMock()
    ns._is_gemini_transport_timeout = lambda exc: isinstance(exc, TransportTimeout)
    ns._mark_model_unavailable = lambda model, why: ns.SESSION_UNAVAILABLE_MODELS.add(model)
    ns._generate_via_chat = generate or (lambda model, *a, **k: "ok")
    ns._apply_deterministic_publication_rescue = rescue or (lambda parsed, rows: (parsed, []))
    return ns


class Run173OperationalYieldTests(unittest.TestCase):
    def test_two_consecutive_transport_timeouts_open_run_local_circuit(self):
        def generate(model, *args, **kwargs):
            raise TransportTimeout("slow")

        p = fake_pipeline(generate=generate)
        with patch.dict(os.environ, {"GEMINI_MODEL_TIMEOUT_CIRCUIT_BREAKER_THRESHOLD": "2"}):
            run173.install(p)
        for _ in range(2):
            with self.assertRaises(TransportTimeout):
                p._generate_via_chat("gemini-3.7-flash", "prompt")
        self.assertIn("gemini-3.7-flash", p.SESSION_UNAVAILABLE_MODELS)
        self.assertEqual(2, p._run173_transport_timeout_streaks["gemini-3.7-flash"])

    def test_successful_response_resets_consecutive_timeout_streak(self):
        sequence = [TransportTimeout("slow"), "ok", TransportTimeout("slow")]

        def generate(model, *args, **kwargs):
            item = sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        p = fake_pipeline(generate=generate)
        run173.install(p)
        with self.assertRaises(TransportTimeout):
            p._generate_via_chat("m1", "prompt")
        self.assertEqual("ok", p._generate_via_chat("m1", "prompt"))
        with self.assertRaises(TransportTimeout):
            p._generate_via_chat("m1", "prompt")
        self.assertNotIn("m1", p.SESSION_UNAVAILABLE_MODELS)
        self.assertEqual(1, p._run173_transport_timeout_streaks["m1"])

    def test_non_transport_error_does_not_open_circuit(self):
        p = fake_pipeline(generate=lambda model, *a, **k: (_ for _ in ()).throw(RuntimeError("bug")))
        run173.install(p)
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                p._generate_via_chat("m1", "prompt")
        self.assertNotIn("m1", p.SESSION_UNAVAILABLE_MODELS)
        self.assertEqual({}, p._run173_transport_timeout_streaks)

    def test_optimizer_audit_vague_multiplier_is_removed_without_new_fact(self):
        draft = (
            ("前段の根拠ある説明です。" * 40)
            + "\n\nAdamWのようなオプティマイザは状態を保持します。これがモデル本体の数倍のメモリを消費する原因になっていました。"
            + "\n\n結論です。"
            + ("補足です。" * 40)
        )
        parsed = {"note_draft": draft, "title": "オプティマイザの判断", "action_text": "小さく比較する"}
        p = fake_pipeline()
        run173.install(p)
        rescued, changes = p._apply_deterministic_publication_rescue(
            parsed,
            [{"reason_code": "FACT_UNSUPPORTED_CLAIM", "message": "unsupported vague quantified claim: 数倍"}],
        )
        self.assertNotIn("数倍", rescued["note_draft"])
        self.assertIn("AdamWのようなオプティマイザは状態を保持します。", rescued["note_draft"])
        self.assertEqual(["run173_vague_quantity_sentence_removed:数倍"], changes)
        self.assertNotEqual(parsed["note_draft"], rescued["note_draft"])

    def test_micro_rescue_declines_when_token_is_in_title_or_action(self):
        draft = "数倍という表現です。" + ("本文です。" * 150)
        parsed = {"note_draft": draft, "title": "数倍というテーマ", "action_text": "確認する"}
        p = fake_pipeline()
        run173.install(p)
        rescued, changes = p._apply_deterministic_publication_rescue(
            parsed,
            [{"reason_code": "FACT_UNSUPPORTED_CLAIM", "message": "unsupported vague quantified claim: 数倍"}],
        )
        self.assertEqual(parsed, rescued)
        self.assertEqual([], changes)

    def test_existing_core_rescue_has_priority(self):
        original = {"note_draft": "本文" * 300}
        core = {"note_draft": "core rescued"}
        p = fake_pipeline(rescue=lambda parsed, rows: (core, ["core_change"]))
        run173.install(p)
        rescued, changes = p._apply_deterministic_publication_rescue(
            original,
            [{"reason_code": "FACT_UNSUPPORTED_CLAIM", "message": "unsupported vague quantified claim: 数倍"}],
        )
        self.assertIs(core, rescued)
        self.assertEqual(["core_change"], changes)

    def test_workflow_contract_keeps_daily_paused_and_normal_member_sync_linked(self):
        root = Path(__file__).resolve().parents[1]
        daily = (root / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
        member = (root / ".github" / "workflows" / "member-presentation-sync.yml").read_text(encoding="utf-8")
        self.assertIn("Daily Intelligence & Content Pipeline [PAUSED]", daily)
        self.assertIn("if: ${{ false }}", daily)
        self.assertNotIn("schedule:", daily)
        self.assertIn("python production_pipeline.py", daily)
        self.assertIn("Daily Intelligence & Content Pipeline", member)
        self.assertNotIn("Daily Intelligence & Content Pipeline [ONE SHOT]", member)


if __name__ == "__main__":
    unittest.main()
