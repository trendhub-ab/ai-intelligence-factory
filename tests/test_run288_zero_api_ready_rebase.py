from __future__ import annotations

import copy
import types
import unittest
from pathlib import Path

import publication_contract as contract
import run288_zero_api_ready_rebase as run288

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "current-ready-metadata-rebase.yml"
MODULE = ROOT / "run288_zero_api_ready_rebase.py"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class Run288TransformTests(unittest.TestCase):
    def specimen(self):
        return (
            "# Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。\n\n"
            "### 元情報\n"
            "- **主一次情報**: [GenRec: Towards LLM-Native Recommendation at Netflix]"
            "(https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3?gi=2e4aa81eb621)\n"
            "- **発見経路**: Hacker News\n"
            "- **公開・更新**: 2026-08-15\n\n"
            "本文はここから。\n"
        )

    def test_exact_one_line_transform_preserves_every_other_byte(self):
        old = self.specimen()
        new = run288.transform_genrec_manuscript(old)
        self.assertNotIn(run288.OLD_LINE, new)
        self.assertIn(run288.NEW_LINE, new)
        self.assertEqual(new.replace(run288.NEW_LINE, run288.OLD_LINE, 1), old)
        before = old.splitlines(keepends=True)
        after = new.splitlines(keepends=True)
        self.assertEqual(sum(1 for a, b in zip(before, after) if a != b), 1)

    def test_wrong_url_or_source_or_date_fails_closed(self):
        base = self.specimen()
        variants = (
            base.replace("netflixtechblog.com/genrec-", "example.com/genrec-"),
            base.replace("Hacker News", "GitHub"),
            base.replace("2026-08-15", "2026-08-16"),
            base + run288.OLD_LINE + "\n",
        )
        for value in variants:
            with self.subTest(value=value[-80:]):
                with self.assertRaises(ValueError):
                    run288.transform_genrec_manuscript(value)

    def test_pre_run287_caption_requires_exact_policy_and_body_hash(self):
        body = self.specimen()
        good = (
            f"{contract.READY_CAPTION_PREFIX}contract={contract.CONTRACT_ID}"
            f"|policy_sha256={run288.PRE_RUN287_POLICY_SHA256}"
            f"|manuscript_sha256={contract.manuscript_sha256(body)}"
        )
        self.assertTrue(run288._is_exact_pre_run287_block(body, good))
        self.assertFalse(run288._is_exact_pre_run287_block(body + "x", good))
        self.assertFalse(run288._is_exact_pre_run287_block(body, good.replace(run288.PRE_RUN287_POLICY_SHA256, "0" * 64)))

    def test_new_block_is_lossless_and_current_contract_valid(self):
        body = run288.transform_genrec_manuscript(self.specimen()) * 30
        block = run288._current_code_block(body)
        roundtrip = "".join(x["text"]["content"] for x in block["code"]["rich_text"])
        caption = "".join(x["text"]["content"] for x in block["code"]["caption"])
        self.assertEqual(roundtrip, body)
        self.assertTrue(contract.is_current_ready_block(body, caption))


class Run288ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.originals = {
            name: getattr(run288.sync, name)
            for name in (
                "NOTION_API_KEY", "SOURCE_DATA_SOURCE_ID", "SOURCE_DATABASE_ID",
                "_query_db", "_source_state", "_block_children", "_request",
                "_source_current_ready_manuscript",
            )
        }

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(run288.sync, name, value)

    def _install_fixture(self, *, conflicting_current=False, duplicate_legacy=False):
        old_body = Run288TransformTests().specimen()
        old_caption = (
            f"{contract.READY_CAPTION_PREFIX}contract={contract.CONTRACT_ID}"
            f"|policy_sha256={run288.PRE_RUN287_POLICY_SHA256}"
            f"|manuscript_sha256={contract.manuscript_sha256(old_body)}"
        )
        legacy = {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": old_body}],
                "caption": [{"plain_text": old_caption}],
            },
        }
        blocks = [legacy]
        if duplicate_legacy:
            blocks.append(copy.deepcopy(legacy))
        if conflicting_current:
            other = old_body.replace("本文はここから。", "別の本文。")
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"plain_text": other}],
                    "caption": [{"plain_text": contract.current_ready_caption(other)}],
                },
            })

        page = {"id": "abc123", "properties": {}}
        state = {
            "source": run288.TARGET_SOURCE,
            "primary_url": "https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3?gi=x",
            "eyecatch_url": "https://example.invalid/eyecatch.png",
            "title": "Netflix GenRec",
        }
        run288.sync.NOTION_API_KEY = "test"
        run288.sync.SOURCE_DATA_SOURCE_ID = "ds"
        run288.sync.SOURCE_DATABASE_ID = ""
        run288.sync._query_db = lambda *a, **k: [page]
        run288.sync._source_state = lambda _page: state
        run288.sync._block_children = lambda _pid: list(blocks)
        written = {"body": ""}

        def request(method, url, json=None):
            self.assertEqual(method, "PATCH")
            block = (json or {}).get("children", [])[0]
            written["body"] = "".join(x["text"]["content"] for x in block["code"]["rich_text"])
            return FakeResponse(200)

        run288.sync._request = request
        run288.sync._source_current_ready_manuscript = lambda _pid: written["body"]
        return old_body, written

    def test_rebase_appends_exactly_transformed_current_block(self):
        old, written = self._install_fixture()
        result = run288.rebase_genrec_ready()
        self.assertEqual(result["status"], "rebased")
        self.assertEqual(result["gemini_calls"], 0)
        self.assertFalse(result["private_draft"])
        self.assertFalse(result["public_release"])
        self.assertEqual(written["body"], run288.transform_genrec_manuscript(old))

    def test_conflicting_current_block_fails_closed(self):
        self._install_fixture(conflicting_current=True)
        with self.assertRaises(RuntimeError):
            run288.rebase_genrec_ready()

    def test_duplicate_exact_legacy_blocks_fail_closed(self):
        self._install_fixture(duplicate_legacy=True)
        with self.assertRaises(RuntimeError):
            run288.rebase_genrec_ready()


class Run288RepositoryContractTests(unittest.TestCase):
    def test_module_is_zero_provider_and_specimen_bound(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn(run288.PRE_RUN287_POLICY_SHA256, text)
        self.assertIn(run288.TARGET_URL_SLUG, text)
        self.assertIn(run288.OLD_LINE, text)
        self.assertIn(run288.NEW_LINE, text)
        for forbidden in ("google.genai", "GEMINI_API_KEY", "generate_content", "generateContent", "playwright", "note.com"):
            self.assertNotIn(forbidden, text)

    def test_workflow_is_manual_zero_model_and_no_draft_or_publication(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertIn("REBASE_GENREC_READY", text)
        self.assertIn("pip install requests", text)
        self.assertIn("python run288_zero_api_ready_rebase.py", text)
        self.assertIn("python note_ready_sync.py", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("production_pipeline.py", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("playwright", text)
        self.assertNotIn("contents: write", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
