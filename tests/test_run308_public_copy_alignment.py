from __future__ import annotations

import unittest

import run308_public_copy_alignment_guard as r308


class Run308PublicCopyAlignmentTests(unittest.TestCase):
    def test_current_repository_surfaces_pass(self):
        self.assertEqual(r308.audit(), [])

    def test_fixed_lp_rejects_stale_product_hunt(self):
        text = f"""## Canonical fixed-note LP copy
{r308.CORE_PROMISE}
自分の開発 業務利用 必要に応じ
GitHub Hacker News ArXiv OfficialVendor Product Hunt
{r308.CURRENT_CTA_LABEL}
## Copy rules
"""
        self.assertIn("run307_fixed_lp_stale_product_hunt", r308._audit_lp(text))

    def test_fixed_lp_rejects_client_primary_legacy_heading(self):
        text = f"""## Canonical fixed-note LP copy
{r308.CORE_PROMISE}
自分の開発 業務利用 必要に応じ
GitHub Hacker News ArXiv OfficialVendor
{r308.CURRENT_CTA_LABEL}
顧客にどう答える？
## Copy rules
"""
        failures = r308._audit_lp(text)
        self.assertTrue(any(item.startswith("run307_fixed_lp_legacy_heading:") for item in failures))

    def test_article_cta_requires_current_label(self):
        stale = 'CTA_LINK_LABEL = "詳しくはこちら"\nこのAI、使える！'
        self.assertIn("article_cta_label_not_current", r308._audit_article_cta(stale))

    def test_paid_route_keeps_public_note_human_only(self):
        stale = f"""## 10. note有料導線
このAI、使える！
{r308.CURRENT_CTA_LABEL}
## 11. next
"""
        self.assertIn("paid_contract_public_note_human_only_missing", r308._audit_paid_contract(stale))

    def test_profile_handoff_rejects_stale_product_hunt(self):
        stale = f"""{r308.CORE_PROMISE}
GitHub Hacker News ArXiv OfficialVendor
## 手動反映用・現行プロフィール/署名
Product Hunt
## 反映ルール
公開noteはhuman-only
"""
        self.assertIn("run308_handoff_profile_stale_product_hunt", r308._audit_handoff(stale))


if __name__ == "__main__":
    unittest.main()
