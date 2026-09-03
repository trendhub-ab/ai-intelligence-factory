from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import publication_contract as contract
import run194_publication_contract as run194


def ready_block(body: str, caption: str) -> dict:
    return {
        "id": "block",
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": [{"plain_text": caption, "text": {"content": caption}}],
        },
    }


class Run194PublicationContractTests(unittest.TestCase):
    def _module(self, blocks=None):
        blocks = list(blocks or [])
        state = {"last_skip": None}

        def build_children(body, caption="AIIF_MANUSCRIPT:READY"):
            return [{"body": body, "caption": caption}]

        module = SimpleNamespace()
        module.build_notion_manuscript_children = build_children
        module._notion_page_manuscript_blocks = lambda page_id, headers: blocks
        module._notion_code_caption = lambda block: "".join(
            item.get("plain_text", "") for item in (block.get("code") or {}).get("caption", [])
        )
        module._notion_page_has_manuscript_child = lambda page_id, headers: False
        module.MANUSCRIPT_CAPTION_READY = "AIIF_MANUSCRIPT:READY"

        def upgrade_notion_page_with_report(
            page_id, repo_name, repo_url, score, score_breakdown_text,
            what_text, why_important_text, why_not_important_text, action_text,
            spdx_id, clean_manuscript, **kwargs
        ):
            state["last_skip"] = module._notion_page_has_manuscript_child(page_id, {})
            return True

        module.upgrade_notion_page_with_report = upgrade_notion_page_with_report
        module._test_state = state
        return module

    def test_policy_sha_changes_when_any_manifest_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in contract.PUBLICATION_POLICY_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{name}:v1", encoding="utf-8")
            first = contract.policy_sha256(root)
            changed = root / contract.PUBLICATION_POLICY_FILES[-1]
            changed.write_text("changed", encoding="utf-8")
            second = contract.policy_sha256(root)
            self.assertNotEqual(first, second)

    def test_missing_manifest_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                contract.policy_sha256(Path(tmp))

    def test_ready_caption_binds_policy_and_exact_body(self) -> None:
        body = "current article"
        caption = contract.current_ready_caption(body)
        self.assertTrue(contract.is_current_ready_caption(caption))
        self.assertTrue(contract.is_current_ready_block(body, caption))
        self.assertFalse(contract.is_current_ready_block(body + " changed", caption))
        self.assertFalse(contract.is_current_ready_caption(contract.LEGACY_READY_CAPTION))

    def test_ready_manuscript_is_stamped_with_content_addressed_contract(self) -> None:
        module = self._module()
        run194.install(module)
        body = "current article"
        children = module.build_notion_manuscript_children(body)
        caption = children[0]["caption"]
        self.assertTrue(contract.is_current_ready_block(body, caption))
        self.assertEqual(contract.CONTRACT_ID, module.CURRENT_PUBLICATION_CONTRACT)
        self.assertEqual(contract.policy_sha256(), module.CURRENT_PUBLICATION_POLICY_SHA256)

    def test_notion_transport_segments_rejoin_to_exact_manuscript_bytes(self) -> None:
        module = self._module()
        module.NOTION_BLOCK_LIMIT = 10

        def lossy_original_builder(body, caption="AIIF_MANUSCRIPT:READY"):
            # Simulate the real Notion payload shape.  The overlay must replace these
            # transport segments with byte-exact slices before persistence.
            return [{
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": body.replace("\n", "")}}],
                    "language": "markdown",
                    "caption": [{"type": "text", "text": {"content": caption}}],
                },
            }]

        module.build_notion_manuscript_children = lossy_original_builder
        run194.install(module)

        body = "123456789\nABCDEFGHIJ\nklmnopqrst\n最後の行"
        children = module.build_notion_manuscript_children(body)
        code = children[0]["code"]
        segments = [item["text"]["content"] for item in code["rich_text"]]
        persisted = "".join(segments)
        caption = code["caption"][0]["text"]["content"]

        self.assertEqual(body, persisted)
        self.assertTrue(all(0 < len(segment) <= module.NOTION_BLOCK_LIMIT for segment in segments))
        self.assertTrue(contract.is_current_ready_block(persisted, caption))

    def test_review_caption_is_not_rewritten_as_ready(self) -> None:
        module = self._module()
        run194.install(module)
        review = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
        children = module.build_notion_manuscript_children("review article", review)
        self.assertEqual(review, children[0]["caption"])

    def test_corrupted_or_legacy_ready_does_not_satisfy_current_guard(self) -> None:
        body = "A" * 250
        valid_caption = contract.current_ready_caption(body)
        module = self._module([
            ready_block(body, contract.LEGACY_READY_CAPTION),
            ready_block(body + "tampered", valid_caption),
        ])
        run194.install(module)
        self.assertFalse(module._notion_page_has_manuscript_child("page", {}))

    def test_latest_valid_body_controls_same_policy_idempotency(self) -> None:
        first = "A" * 250
        latest = "B" * 250
        blocks = [
            ready_block(first, contract.current_ready_caption(first)),
            ready_block(latest, contract.current_ready_caption(latest)),
        ]
        module = self._module(blocks)
        run194.install(module)

        common = ("page", "repo", "url", 80, "score", "what", "why", "why-not", "action", "MIT")
        module.upgrade_notion_page_with_report(*common, first)
        self.assertFalse(module._test_state["last_skip"], "an older matching block must not suppress a newer regeneration")

        module.upgrade_notion_page_with_report(*common, latest)
        self.assertTrue(module._test_state["last_skip"], "latest byte-identical body should remain idempotent")

    def test_overlay_adds_no_model_or_public_release_surface(self) -> None:
        source = inspect.getsource(run194)
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
