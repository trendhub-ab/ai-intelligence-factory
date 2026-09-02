from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace

import publication_contract as contract
import run194_publication_contract as run194


class Run194PublicationContractTests(unittest.TestCase):
    def _module(self, blocks=None):
        blocks = list(blocks or [])

        def build_children(body, caption="AIIF_MANUSCRIPT:READY"):
            return [{"body": body, "caption": caption}]

        return SimpleNamespace(
            build_notion_manuscript_children=build_children,
            _notion_page_manuscript_blocks=lambda page_id, headers: blocks,
            _notion_code_caption=lambda block: block.get("caption", ""),
            MANUSCRIPT_CAPTION_READY="AIIF_MANUSCRIPT:READY",
        )

    def test_contract_names_current_article_and_eyecatch_policy(self) -> None:
        self.assertIn("run172-run183", contract.CURRENT_READY_CAPTION)
        self.assertIn("run175-run176+reader-value-review", contract.CURRENT_READY_CAPTION)
        self.assertIn("run178-run183", contract.CURRENT_READY_CAPTION)
        self.assertTrue(contract.is_current_ready_caption(contract.CURRENT_READY_CAPTION))
        self.assertFalse(contract.is_current_ready_caption(contract.LEGACY_READY_CAPTION))

    def test_ready_manuscript_is_stamped_with_exact_current_contract(self) -> None:
        module = self._module()
        run194.install(module)
        children = module.build_notion_manuscript_children("current article")
        self.assertEqual(contract.CURRENT_READY_CAPTION, children[0]["caption"])
        self.assertEqual(contract.CONTRACT_ID, module.CURRENT_PUBLICATION_CONTRACT)

    def test_review_caption_is_not_rewritten_as_ready(self) -> None:
        module = self._module()
        run194.install(module)
        review = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
        children = module.build_notion_manuscript_children("review article", review)
        self.assertEqual(review, children[0]["caption"])

    def test_legacy_ready_block_no_longer_satisfies_idempotency_guard(self) -> None:
        module = self._module([{"caption": contract.LEGACY_READY_CAPTION}])
        run194.install(module)
        self.assertFalse(module._notion_page_has_manuscript_child("page", {}))

    def test_current_ready_block_satisfies_idempotency_guard(self) -> None:
        module = self._module([{"caption": contract.CURRENT_READY_CAPTION}])
        run194.install(module)
        self.assertTrue(module._notion_page_has_manuscript_child("page", {}))

    def test_overlay_adds_no_model_or_public_release_surface(self) -> None:
        source = inspect.getsource(run194)
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
