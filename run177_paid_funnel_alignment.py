"""Run177: align the free-note CTA with the finalized paid-member funnel.

This runtime layer is deliberately narrow:
- keep article_id / UTM / aif_article_id tracking logic in pipeline.py unchanged;
- keep SUBSCRIPTION_LANDING_URL dynamic (Repository Variable supplied at runtime);
- change only the reader-facing CTA copy/product naming;
- make zero Gemini/model requests and perform no writes by itself.
"""
from __future__ import annotations


def install(pipeline_module):
    """Install the finalized reader-facing subscription CTA without touching attribution."""

    def build_subscription_cta(article_id: str, tracking_url: str = "") -> str:
        url = tracking_url or pipeline_module.build_subscription_tracking_url(article_id)
        if not url:
            return ""
        return (
            f"{pipeline_module.DIVIDER_LINE}"
            "### 「自分はどうする？」まで判断したい方へ\n\n"
            "無料noteでは、重要なAI・IT情報を分かりやすくお届けしています。"
            "会員向けの **AI Decision Intelligence** では、"
            "「使う・試す・待つ・見送る」の視点で、仕事の判断に必要な情報を整理しています。"
            "会員向けDigestもご利用いただけます。\n\n"
            f"[AI Decision Intelligenceについて見る]({url})\n"
        )

    pipeline_module.build_subscription_cta = build_subscription_cta
    return pipeline_module
