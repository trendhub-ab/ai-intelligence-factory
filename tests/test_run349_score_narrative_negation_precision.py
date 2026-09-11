from __future__ import annotations

from types import SimpleNamespace
import unittest

from production_pipeline import (
    _all_low_score_urgency_mentions_are_explicitly_rejected,
    install_run349_score_narrative_negation_precision,
)


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(message % args if args else str(message))


class Run349ScoreNarrativeNegationPrecisionTests(unittest.TestCase):
    def _pipeline(self):
        def base_gate(parsed, source_context="", source_info=None):
            # Model the exact pre-Run349 publication outcome from real Run38.
            article = str((parsed or {}).get("note_draft") or "")
            if any(token in article for token in ("今すぐ", "直ちに", "全面導入", "全面移行", "必ず導入")):
                return "REVIEW", ["score_narrative_mismatch"]
            return "PASS", []

        return SimpleNamespace(validate_publication_readiness_gate=base_gate, logger=_Logger())

    def test_real_run38_negative_full_migration_sentence_is_rescued(self):
        article = (
            "本研究は仮想環境における基礎的な概念実証です。"
            "実運用中のエージェントから手動の停止ルールを外し、"
            "この内部ドライブ方式に全面移行するのはリスクが高すぎます。"
        )
        self.assertTrue(_all_low_score_urgency_mentions_are_explicitly_rejected(article))
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        state, issues = p.validate_publication_readiness_gate(
            {"score": 59, "note_draft": article, "action_text": "制御ルールの依存度を可視化する。"}
        )
        self.assertEqual("PASS", state)
        self.assertEqual([], issues)
        self.assertTrue(any("RUN349 SCORE NARRATIVE PRECISION" in row for row in p.logger.messages))

    def test_positive_full_migration_remains_blocked(self):
        article = "成果が有望なので、この内部ドライブ方式に全面移行するべきです。"
        self.assertFalse(_all_low_score_urgency_mentions_are_explicitly_rejected(article))
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        self.assertEqual(
            ("REVIEW", ["score_narrative_mismatch"]),
            p.validate_publication_readiness_gate({"score": 59, "note_draft": article}),
        )

    def test_risk_acknowledgement_but_positive_action_remains_blocked(self):
        article = "全面移行にはリスクがありますが、それでも実施するべきです。"
        self.assertFalse(_all_low_score_urgency_mentions_are_explicitly_rejected(article))
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        self.assertEqual(
            ("REVIEW", ["score_narrative_mismatch"]),
            p.validate_publication_readiness_gate({"score": 59, "note_draft": article}),
        )

    def test_mixed_negative_and_positive_urgency_fails_closed(self):
        article = (
            "全面移行するのはリスクが高すぎます。"
            "ただし別部門では今すぐ導入すべきです。"
        )
        self.assertFalse(_all_low_score_urgency_mentions_are_explicitly_rejected(article))
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        self.assertEqual(
            ("REVIEW", ["score_narrative_mismatch"]),
            p.validate_publication_readiness_gate({"score": 59, "note_draft": article}),
        )

    def test_explicit_do_not_rush_is_rescued(self):
        for article in (
            "今すぐ導入する必要はありません。まず観察します。",
            "全面導入は避け、限定検証に留めます。",
            "直ちに切り替える必要はないため、現状を維持します。",
        ):
            self.assertTrue(_all_low_score_urgency_mentions_are_explicitly_rejected(article), article)

    def test_score_above_low_band_is_never_changed(self):
        article = "全面移行するのはリスクが高すぎます。"
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        self.assertEqual(
            ("REVIEW", ["score_narrative_mismatch"]),
            p.validate_publication_readiness_gate({"score": 80, "note_draft": article}),
        )

    def test_other_publication_issues_are_preserved(self):
        def base_gate(parsed, source_context="", source_info=None):
            return "REVIEW", ["score_narrative_mismatch", "primary_evidence_insufficient"]

        p = SimpleNamespace(validate_publication_readiness_gate=base_gate, logger=_Logger())
        install_run349_score_narrative_negation_precision(p)
        state, issues = p.validate_publication_readiness_gate(
            {"score": 59, "note_draft": "全面移行するのはリスクが高すぎます。"}
        )
        self.assertEqual("REVIEW", state)
        self.assertEqual(["primary_evidence_insufficient"], issues)

    def test_install_is_idempotent(self):
        p = self._pipeline()
        install_run349_score_narrative_negation_precision(p)
        first = p.validate_publication_readiness_gate
        install_run349_score_narrative_negation_precision(p)
        self.assertIs(first, p.validate_publication_readiness_gate)


if __name__ == "__main__":
    unittest.main()
