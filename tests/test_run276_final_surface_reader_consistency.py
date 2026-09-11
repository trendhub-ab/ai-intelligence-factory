from __future__ import annotations

import inspect
import types
import unittest

import reader_quality_precision as precision
import run249_final_publication_surface_gate as r249


def _base_signals(**overrides):
    base = {
        "technical_terms_per_1000_chars": 12.0,
        "opening_technical_terms_per_1000_chars": 12.0,
        "plain_language_bridge_present": True,
        "jargon_dense_paragraph_count": 0,
        "implementation_identifier_count": 0,
        "analogy_hits": 0,
        "analogy_used": False,
        "unexplained_jargon": [],
        "bridge_needed": False,
        "opening_non_engineer_access": "GOOD",
        "reader_temperature_rhythm": "GOOD",
        "max_explanatory_paragraph_run": 1,
        "jargon_translation": "GOOD",
        "non_engineer_core_clarity": "GOOD",
        "plain_language_bridge": "GOOD",
        "accessibility_issues": [],
        "accessibility": "GOOD",
        "enjoyment_issues": [],
        "reader_enjoyment": "GOOD",
        "narrative_pull": "GOOD",
        "curiosity_pull": "GOOD",
        "information_budget": "GOOD",
    }
    base.update(overrides)
    return base


def _healthy_reader_axes():
    return {
        "accessibility": "GOOD",
        "curiosity_pull": "GOOD",
        "reader_enjoyment": "GOOD",
        "narrative_pull": "GOOD",
        "jargon_translation": "GOOD",
        "non_engineer_core_clarity": "GOOD",
        "information_budget": "GOOD",
        "reader_temperature_rhythm": "GOOD",
    }


def _weak_reader_axes():
    return {
        "accessibility": "REVIEW",
        "curiosity_pull": "GOOD",
        "reader_enjoyment": "REVIEW",
        "narrative_pull": "GOOD",
        "jargon_translation": "REVIEW",
        "non_engineer_core_clarity": "REVIEW",
        "information_budget": "REVIEW",
        "reader_temperature_rhythm": "GOOD",
    }


def _builder(article, repo_name, repo_url, spdx_id, source, **kwargs):
    return r249._projection_from_parts(
        kwargs.get("title_text", ""),
        kwargs.get("reader_summary") or {},
        article,
    )


def _pipeline(summary, signal_fn):
    return types.SimpleNamespace(
        logger=types.SimpleNamespace(warning=lambda *args, **kwargs: None),
        validate_human_appeal_gate=lambda parsed, peer_articles=None: ("ACCEPTABLE", []),
        build_clean_note_manuscript=_builder,
        build_reader_first_summary=lambda parsed: dict(summary),
        _reader_experience_signals=signal_fn,
    )


class Run276FinalSurfaceReaderConsistencyTests(unittest.TestCase):
    def test_run32_nominal_topic_anchors_are_not_repeated_insight(self):
        # Run32's real false-positive shape was exactly three recurring 7-char topic anchors:
        # エージェントの / エージェントが / すべてのデータ. They name the subject; they do not
        # repeat a conclusion or recommendation.
        article = "\n\n".join([
            "エージェントの設計では、入力を整理して判断材料を分けます。",
            "すべてのデータを一度に渡す方式とは異なります。",
            "エージェントが参照する情報には優先順位があります。",
            "すべてのデータを保持することが目的ではありません。",
            "エージェントの役割は必要な情報を選ぶことです。",
            "エージェントが使う情報源も条件ごとに変わります。",
            "すべてのデータを同じ重みで扱うわけではありません。",
            "エージェントの構成は用途に応じて分かれます。",
        ])
        repeated = precision._repeated_cross_paragraph_fragments(article)
        self.assertGreaterEqual(len(repeated), 3)
        self.assertFalse(precision._has_semantic_repetitive_insight(article))

        fixed = precision.correct_reader_signals(
            article,
            _base_signals(
                enjoyment_issues=["repetitive_insight"],
                reader_enjoyment="REVIEW",
            ),
        )
        self.assertNotIn("repetitive_insight", fixed["enjoyment_issues"])
        self.assertEqual(fixed["reader_enjoyment"], "GOOD")
        self.assertTrue(fixed["run276_semantic_repetition_precision"])

    def test_genuine_repeated_judgment_remains_repetitive_insight(self):
        repeated_judgment = "現時点では限定導入する価値があります。"
        article = "\n\n".join([
            repeated_judgment + "最初は小さな範囲で確認します。",
            repeated_judgment + "次に条件差を比較します。",
            repeated_judgment + "最後に運用条件を確かめます。",
        ])
        self.assertTrue(precision._has_semantic_repetitive_insight(article))
        fixed = precision.correct_reader_signals(
            article,
            _base_signals(
                enjoyment_issues=["repetitive_insight"],
                reader_enjoyment="REVIEW",
            ),
        )
        self.assertIn("repetitive_insight", fixed["enjoyment_issues"])
        self.assertEqual(fixed["reader_enjoyment"], "REVIEW")

    def test_compact_summary_cannot_manufacture_long_form_reader_failure(self):
        summary = {
            "what": "複数のAIエージェントが情報を集める条件を比較した研究です。",
            "why": "情報量を増やすだけでは判断が良くならない条件を確認できます。",
            "decision": "まず限定した条件で比較し、効果が出る範囲を確かめます。",
        }

        def signals(text):
            # This simulates the exact pre-Run276 category bug: when a compact header is prepended,
            # long-form density diagnostics report many REVIEW axes even though the article body is
            # healthy. Run276 must not ask the long-form evaluator to classify that combined shape.
            if "30秒でわかるこの記事" in text:
                return _weak_reader_axes()
            return _healthy_reader_axes()

        pipe = _pipeline(summary, signals)
        r249.install(pipe)
        state, issues = pipe.validate_human_appeal_gate(
            {"title_text": "AIエージェントの情報量をどう考えるか。", "note_draft": "本文は平易です。"},
            [],
        )
        self.assertEqual(state, "ACCEPTABLE")
        self.assertFalse(any("final_surface_multi_axis_reader_weakness" in x for x in issues))

    def test_summary_fragment_still_blocks_after_run276(self):
        summary = {
            "what": "新しい研究が公開されました。",
            "why": "判断条件を比較できるため、",
            "decision": "まず限定条件で比較します。",
        }
        pipe = _pipeline(summary, lambda text: _healthy_reader_axes())
        r249.install(pipe)
        state, issues = pipe.validate_human_appeal_gate(
            {"title_text": "判断条件を比較する。", "note_draft": "本文は平易です。"},
            [],
        )
        self.assertEqual(state, "WEAK")
        self.assertTrue(any("final_surface_summary_fragment:なぜ重要？" in x for x in issues))

    def test_genuinely_jargon_dense_summary_cluster_still_blocks(self):
        summary = {
            "what": "MCP RPC CUDA VRAM Kubernetes gRPC の各レイヤーを同時に接続する構成が公開されました。",
            "why": "CLI SDK ABI NUMA RDMA WebSocket の境界条件を理解しないと運用判断を誤る可能性があります。",
            "decision": "まず限定した環境で確認します。",
        }
        pipe = _pipeline(summary, lambda text: _healthy_reader_axes())
        r249.install(pipe)
        state, issues = pipe.validate_human_appeal_gate(
            {"title_text": "複雑な構成をどう判断するか。", "note_draft": "本文は平易です。"},
            [],
        )
        self.assertEqual(state, "WEAK")
        self.assertTrue(any("final_surface_summary_jargon_cluster" in x for x in issues))

    def test_final_surface_does_not_duplicate_body_reader_weakness(self):
        summary = {
            "what": "新しい研究が公開されました。",
            "why": "実務条件を比較できます。",
            "decision": "まず限定条件で比較します。",
        }
        pipe = _pipeline(summary, lambda text: _weak_reader_axes())
        r249.install(pipe)
        state, issues = pipe.validate_human_appeal_gate(
            {"title_text": "研究結果をどう使うか。", "note_draft": "本文自体が高密度な想定です。"},
            [],
        )
        # Run248/body Reader validation is the authoritative owner for article-wide axes.
        # Run249 must only add defects introduced or exposed by the late public surface.
        self.assertEqual(state, "ACCEPTABLE")
        self.assertFalse(any("final_surface_multi_axis_reader_weakness" in x for x in issues))
        self.assertFalse(any("final_surface_non_engineer_access_failure" in x for x in issues))

    def test_run276_precision_adds_no_provider_or_model_call_site(self):
        source = inspect.getsource(precision) + "\n" + inspect.getsource(r249)
        self.assertNotIn("generateContent", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("requests.get(", source)
        self.assertNotIn("requests.post(", source)
        self.assertTrue(r249.RUN249_ZERO_PROVIDER_CALLS)
        self.assertTrue(r249.RUN276_SUMMARY_AWARE_FINAL_SURFACE)
        self.assertTrue(r249.RUN354_BODY_READER_DEDUP)


if __name__ == "__main__":
    unittest.main()
