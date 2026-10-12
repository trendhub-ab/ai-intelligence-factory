from __future__ import annotations

import unittest
from types import SimpleNamespace

import publication_contract as contract
import run194_publication_contract as run194


def ready_block(block_id: str, body: str) -> dict:
    caption = contract.current_ready_caption(body)
    return {
        "id": block_id,
        "type": "code",
        "code": {
            "language": "markdown",
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": [{"plain_text": caption, "text": {"content": caption}}],
        },
    }


def review_block(block_id: str, body: str) -> dict:
    caption = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
    return {
        "id": block_id,
        "type": "code",
        "code": {
            "language": "markdown",
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": [{"plain_text": caption, "text": {"content": caption}}],
        },
    }


class Run194SingleCanonicalManuscriptTests(unittest.TestCase):
    def _module(self, initial_blocks: list[dict], *, cleanup_deletes: bool = True, upgrade_result: bool = True):
        blocks = list(initial_blocks)
        state = {"cleanup_calls": [], "pending_reasons": []}
        module = SimpleNamespace()
        module.MANUSCRIPT_CAPTION_READY = "AIIF_MANUSCRIPT:READY"
        module.MANUSCRIPT_CAPTION_REVIEW = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
        module.build_notion_manuscript_children = lambda body, caption="AIIF_MANUSCRIPT:READY": [
            {"body": body, "caption": caption}
        ]
        module._notion_page_manuscript_blocks = lambda page_id, headers: list(blocks)
        module._notion_code_caption = lambda block: "".join(
            item.get("plain_text", "") for item in (block.get("code") or {}).get("caption", [])
        )
        module._notion_page_has_manuscript_child = lambda page_id, headers: bool(blocks)

        def rollback(block_ids, repo_name, headers):
            ids = list(block_ids)
            state["cleanup_calls"].append(ids)
            if cleanup_deletes:
                blocks[:] = [block for block in blocks if block.get("id") not in set(ids)]

        module._rollback_notion_manuscript_children = rollback
        module._mark_pending_retry_or_escalate = lambda page_id, repo_name, reason: state["pending_reasons"].append(reason)

        def upgrade_notion_page_with_report(
            page_id, repo_name, repo_url, score, score_breakdown_text,
            what_text, why_important_text, why_not_important_text, action_text,
            spdx_id, clean_manuscript, **kwargs
        ):
            if not upgrade_result:
                return False
            if not module._notion_page_has_manuscript_child(page_id, {}):
                blocks.append(ready_block(f"new-{len(blocks)}", clean_manuscript))
            return True

        module.upgrade_notion_page_with_report = upgrade_notion_page_with_report
        module._test_blocks = blocks
        module._test_state = state
        return module

    @staticmethod
    def _upgrade(module, body: str) -> bool:
        common = ("page", "repo", "url", 80, "score", "what", "why", "why-not", "action", "MIT")
        return module.upgrade_notion_page_with_report(*common, body)

    def test_successful_ready_save_converges_old_and_review_manuscripts_to_one_exact_current_block(self):
        old = "old ready draft"
        expected = "final canonical draft"
        module = self._module([
            ready_block("old-ready", old),
            review_block("old-review", "editorial retry draft"),
        ])
        run194.install(module)

        self.assertTrue(self._upgrade(module, expected))
        self.assertEqual(1, len(module._test_blocks))
        remaining = module._test_blocks[0]
        self.assertEqual(expected, run194._block_body(remaining))
        self.assertTrue(
            contract.is_exact_current_ready_block(
                run194._block_body(remaining),
                module._notion_code_caption(remaining),
                expected,
            )
        )

    def test_existing_exact_duplicate_ready_blocks_are_collapsed_without_reappend(self):
        expected = "same canonical draft"
        module = self._module([
            ready_block("duplicate-1", expected),
            ready_block("duplicate-2", expected),
        ])
        run194.install(module)

        self.assertTrue(self._upgrade(module, expected))
        self.assertEqual(["duplicate-2"], [block.get("id") for block in module._test_blocks])

    def test_cleanup_verification_failure_fails_closed_to_pending_retry(self):
        old = "old ready draft"
        expected = "final canonical draft"
        module = self._module([ready_block("old-ready", old)], cleanup_deletes=False)
        run194.install(module)

        self.assertFalse(self._upgrade(module, expected))
        self.assertTrue(module._test_state["cleanup_calls"])
        self.assertEqual(1, len(module._test_state["pending_reasons"]))
        self.assertIn("canonical manuscript", module._test_state["pending_reasons"][0].lower())

    def test_failed_original_upgrade_preserves_existing_manuscripts_and_skips_canonical_cleanup(self):
        existing = "existing safe draft"
        module = self._module([ready_block("existing", existing)], upgrade_result=False)
        run194.install(module)

        self.assertFalse(self._upgrade(module, "new failed draft"))
        self.assertEqual(["existing"], [block.get("id") for block in module._test_blocks])
        self.assertEqual([], module._test_state["cleanup_calls"])
        self.assertEqual([], module._test_state["pending_reasons"])


if __name__ == "__main__":
    unittest.main()
