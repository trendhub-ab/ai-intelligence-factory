import copy
import unittest

import editorial_naturalness as en
import pipeline


class Run240EditorialNaturalnessIntegrationTests(unittest.TestCase):
    def test_pure_wrappers_match_canonical_module(self):
        parsed = {
            "note_draft": "## 導入\n原資料で仕様を確認できる。一方で課題もある。私なら小さく比較テストをしたい。",
            "action_text": "限定環境で検証したい。",
        }
        article = parsed["note_draft"]
        self.assertEqual(pipeline._classify_article_claims(parsed), en.classify_article_claims(parsed))
        self.assertEqual(pipeline._find_fabricated_personal_experience(article), en.find_fabricated_personal_experience(article))
        self.assertEqual(pipeline._sentence_shingles(article), en.sentence_shingles(article))
        self.assertEqual(pipeline._human_editorial_depth_signals(article), en.human_editorial_depth_signals(article))
        self.assertEqual(pipeline._style_sequence(article), en.style_sequence(article))
        self.assertEqual(pipeline._rhetorical_template_phrases(article), en.rhetorical_template_phrases(article))

    def test_ai_style_wrapper_reads_live_display_variants(self):
        original = pipeline.ARTICLE_DISPLAY_VARIANTS
        try:
            custom = [{k: f"LIVE-{k}" for k in ("intro", "conclusion", "why", "what", "key", "decision", "final")}]
            pipeline.ARTICLE_DISPLAY_VARIANTS = custom
            article = "\n\n".join(f"## LIVE-{k}\n本文です。" for k in ("intro", "conclusion", "why", "what", "key", "decision", "final"))
            self.assertEqual(
                pipeline._ai_style_composite_signals(article),
                en.ai_style_composite_signals(article, custom),
            )
        finally:
            pipeline.ARTICLE_DISPLAY_VARIANTS = original

    def test_cross_article_wrapper_reads_live_peer_memory_and_opening_helper(self):
        original_memory = copy.deepcopy(pipeline._RUN_ARTICLE_STYLE_MEMORY)
        try:
            article = "## 導入\nこれは読者向けの導入です。" + ("そのため、比較して判断します。" * 12)
            peer = {
                "name": "peer",
                "sequence": en.style_sequence(article),
                "opening_shingles": tuple(en.sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)),
                "heading_count": 1,
                "rhetorical_phrases": tuple(en.rhetorical_template_phrases(article)),
            }
            pipeline._RUN_ARTICLE_STYLE_MEMORY[:] = [peer]
            expected = en.cross_article_naturalness_signals(article, [peer], pipeline._article_opening_excerpt)
            self.assertEqual(pipeline._cross_article_naturalness_signals(article), expected)
        finally:
            pipeline._RUN_ARTICLE_STYLE_MEMORY[:] = original_memory


if __name__ == "__main__":
    unittest.main()
