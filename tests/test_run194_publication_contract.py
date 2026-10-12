from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import publication_contract as contract
import run194_publication_contract as run194


def ready_block(body: str, caption: str, block_id: str = "block") -> dict:
    return {
        "id": block_id,
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": [{"plain_text": caption, "text": {"content": caption}}],
        },
    }


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class Run194PublicationContractTests(unittest.TestCase):
    def _module(self, blocks=None):
        blocks = list(blocks or [])
        state = {"last_skip": None, "pending": 0}

        def build_children(body, caption="AIIF_MANUSCRIPT:READY"):
            return [{"body": body, "caption": caption}]

        module = SimpleNamespace()
        module.build_notion_manuscript_children = build_children
        module._notion_page_manuscript_blocks = lambda page_id, headers: list(blocks)
        module._notion_code_caption = lambda block: "".join(
            item.get("plain_text", "") for item in (block.get("code") or {}).get("caption", [])
        )
        module._notion_page_has_manuscript_child = lambda page_id, headers: False
        module.MANUSCRIPT_CAPTION_READY = "AIIF_MANUSCRIPT:READY"
        module.MANUSCRIPT_CAPTION_REVIEW = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
        module.NOTION_API_KEY = "test-key"
        module.NOTION_BLOCK_LIMIT = 1900
        module._notion_headers = lambda: {}
        module.logger = SimpleNamespace(
            info=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        )
        module._mark_pending_retry_or_escalate = lambda *args, **kwargs: state.__setitem__("pending", state["pending"] + 1)

        class Requests:
            @staticmethod
            def patch(url, json=None, headers=None, timeout=None):
                if url.endswith("/children"):
                    child = ((json or {}).get("children") or [{}])[0]
                    body = child.get("body", "")
                    caption = child.get("caption", "")
                    blocks.append(ready_block(body, caption, f"appended-{len(blocks)+1}"))
                    return _Response(200, {"results": [{"id": blocks[-1]["id"]}]})
                return _Response(200)

            @staticmethod
            def delete(url, headers=None, timeout=None):
                block_id = url.rsplit("/", 1)[-1]
                blocks[:] = [block for block in blocks if block.get("id") != block_id]
                return _Response(200)

        module.requests = Requests

        def upgrade_notion_page_with_report(
            page_id, repo_name, repo_url, score, score_breakdown_text,
            what_text, why_important_text, why_not_important_text, action_text,
            spdx_id, clean_manuscript, **kwargs
        ):
            state["last_skip"] = module._notion_page_has_manuscript_child(page_id, {})
            return True

        module.upgrade_notion_page_with_report = upgrade_notion_page_with_report
        module.persist_notion_needs_editorial_review = lambda *args, **kwargs: True
        module.PROP_STATUS = "Status"
        module.STATUS_DEEP_DIVE = "Deep Dive"
        module.PROP_CONTENT_STATUS = "Content Status"
        module.CONTENT_STATUS_DEEP_DIVE = "Deep Dive"
        module.PROP_ARTICLE_STATUS = "Article Status"
        module.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
        module.PROP_SUBSCRIPTION_VISIBILITY = "Subscription Visibility"
        module.VISIBILITY_SUBSCRIBER_ONLY = "Subscriber Only"
        module.PROP_REVIEW_STATUS = "Review Status"
        module._test_state = state
        module._test_blocks = blocks
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

    def test_canonical_article_contract_is_publication_fingerprinted(self) -> None:
        self.assertIn("canonical_article_contract.py", contract.PUBLICATION_POLICY_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in contract.PUBLICATION_POLICY_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{name}:v1", encoding="utf-8")
            first = contract.policy_sha256(root)
            canonical = root / "canonical_article_contract.py"
            canonical.write_text("canonical-article-contract:v2", encoding="utf-8")
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
            ready_block(body, contract.LEGACY_READY_CAPTION, "legacy"),
            ready_block(body + "tampered", valid_caption, "tampered"),
        ])
        run194.install(module)
        self.assertFalse(module._notion_page_has_manuscript_child("page", {}))

    def test_expected_body_becomes_only_canonical_before_upgrade(self) -> None:
        old = "A" * 250
        expected = "B" * 250
        module = self._module([
            ready_block(old, contract.current_ready_caption(old), "old"),
            ready_block(expected, contract.current_ready_caption(expected), "expected"),
        ])
        run194.install(module)

        common = ("page", "repo", "url", 80, "score", "what", "why", "why-not", "action", "MIT")
        self.assertTrue(module.upgrade_notion_page_with_report(*common, expected))
        self.assertTrue(module._test_state["last_skip"])
        self.assertEqual([block["id"] for block in module._test_blocks], ["expected"])

    def test_missing_expected_body_is_appended_then_becomes_only_canonical(self) -> None:
        old = "A" * 250
        expected = "B" * 250
        module = self._module([
            ready_block(old, contract.current_ready_caption(old), "old"),
        ])
        run194.install(module)

        common = ("page", "repo", "url", 80, "score", "what", "why", "why-not", "action", "MIT")
        self.assertTrue(module.upgrade_notion_page_with_report(*common, expected))
        self.assertEqual(len(module._test_blocks), 1)
        final = module._test_blocks[0]
        self.assertEqual(run194._block_body(final), expected)
        self.assertTrue(contract.is_current_ready_block(expected, module._notion_code_caption(final)))

    def test_overlay_adds_no_model_or_public_release_surface(self) -> None:
        source = inspect.getsource(run194)
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
