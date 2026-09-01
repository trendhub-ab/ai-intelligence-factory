from types import SimpleNamespace
import unittest

import run177_paid_funnel_alignment as run177


class Run177PaidFunnelAlignmentTest(unittest.TestCase):
    def _pipeline(self, generated_url="https://example.test/lp?utm_source=note"):
        return SimpleNamespace(
            DIVIDER_LINE="\n---\n",
            build_subscription_tracking_url=lambda article_id: generated_url,
            build_subscription_cta=lambda article_id, tracking_url="": "OLD CTA",
        )

    def test_installs_finalized_member_cta_copy(self):
        pipeline = self._pipeline()
        run177.install(pipeline)

        cta = pipeline.build_subscription_cta("aif-test")

        self.assertIn("「自分はどうする？」まで判断したい方へ", cta)
        self.assertIn("AI Decision Intelligence", cta)
        self.assertIn("使う・試す・待つ・見送る", cta)
        self.assertIn("会員向けDigest", cta)
        self.assertIn("AI Decision Intelligenceについて見る", cta)
        self.assertNotIn("月次サマリー", cta)
        self.assertNotIn("会員向け意思決定DB＋月次サマリー", cta)

    def test_keeps_tracking_url_dynamic(self):
        expected = (
            "https://note.com/trendhub_biz/n/example"
            "?utm_source=note&utm_medium=free_article"
            "&utm_campaign=campaign&utm_content=aif-test&aif_article_id=aif-test"
        )
        pipeline = self._pipeline(generated_url=expected)
        run177.install(pipeline)

        cta = pipeline.build_subscription_cta("aif-test")

        self.assertIn(f"]({expected})", cta)

    def test_explicit_tracking_url_is_preserved(self):
        pipeline = self._pipeline(generated_url="https://should-not-be-used.test")
        run177.install(pipeline)
        supplied = "https://example.test/landing?utm_content=aif-supplied"

        cta = pipeline.build_subscription_cta("aif-test", supplied)

        self.assertIn(f"]({supplied})", cta)
        self.assertNotIn("should-not-be-used", cta)

    def test_missing_tracking_url_fails_closed(self):
        pipeline = self._pipeline(generated_url="")
        run177.install(pipeline)

        self.assertEqual("", pipeline.build_subscription_cta("aif-test"))


if __name__ == "__main__":
    unittest.main()
