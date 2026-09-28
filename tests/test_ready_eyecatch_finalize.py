from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import Mock, patch

import ready_eyecatch_finalize as target


SYNC_ID = "3e8479ffdca9811db058ccf7d711dd88"
TITLE = "OpenAIが最新モデルの開発を停止。自律型AIの制御不能な挙動が突きつけた実務の壁。"
BODY = f"""# {TITLE}

## どんな内容？
OpenAIが最新モデルのトレーニングを一時停止した事例です。

## なぜ重要？
AIエージェントの挙動を制御する運用設計が重要になるためです。
"""


class ReadyEyecatchFinalizeTests(TestCase):
    def test_sync_id_normalization_accepts_notion_uuid(self):
        self.assertEqual(
            target._normalize_sync_id("3e8479ff-dca9-811d-b058-ccf7d711dd88"),
            SYNC_ID,
        )

    def test_reader_summary_uses_reader_first_section(self):
        self.assertEqual(
            target._reader_summary(BODY),
            "OpenAIが最新モデルのトレーニングを一時停止した事例です。",
        )

    def test_already_current_asset_is_zero_mutation(self):
        page = {"id": SYNC_ID}
        state = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "source": "HackerNews",
            "eyecatch_url": "https://example.invalid/current.png",
        }
        with patch.dict(os.environ, {"NOTION_API_KEY": "x", "GH_PAT": "y"}, clear=False), \
             patch.object(target, "_source_page", return_value=page), \
             patch.object(target.ready_sync, "_source_state", return_value=state), \
             patch.object(target.ready_sync, "_source_current_ready_manuscript", return_value=BODY), \
             patch.object(target.eyecatch_contract, "current_asset_url", return_value=True), \
             patch.object(target.pipeline, "generate_note_editorial_eyecatch") as generate, \
             patch.object(target, "_patch_source_eyecatch") as mutate:
            result = target.finalize_ready_eyecatch(SYNC_ID)

        self.assertEqual(result["status"], "ready_eyecatch_already_current")
        self.assertTrue(result["body_unchanged"])
        self.assertFalse(result["article_regeneration"])
        self.assertFalse(result["note_mutation"])
        generate.assert_not_called()
        mutate.assert_not_called()

    def test_finalize_changes_only_eyecatch_property(self):
        page = {"id": SYNC_ID}
        before = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "source": "HackerNews",
            "eyecatch_url": "",
        }
        after = dict(before, eyecatch_url="https://example.invalid/new.png")
        fake_font = Mock()
        fake_font.getname.return_value = ("Noto Sans JP", "Regular")

        class FakeImage:
            size = (1280, 670)
            mode = "RGB"
            def __enter__(self): return self
            def __exit__(self, *args): return False

        with patch.dict(os.environ, {"NOTION_API_KEY": "x", "GH_PAT": "y"}, clear=False), \
             patch.object(target, "_source_page", side_effect=[page, page]), \
             patch.object(target.ready_sync, "_source_state", side_effect=[before, after]), \
             patch.object(target.ready_sync, "_source_current_ready_manuscript", side_effect=[BODY, BODY]), \
             patch.object(target.eyecatch_contract, "current_asset_url", return_value=False), \
             patch.object(target.run179, "ensure_google_font_assets", return_value={str(target.run179.NOTO_SANS_JP_PATH): True}), \
             patch.object(target.run179, "require_production_japanese_font"), \
             patch.object(target.production_pipeline, "install_runtime_layers"), \
             patch.object(target.pipeline, "infer_editorial_category", return_value="AI BUSINESS"), \
             patch.object(target.pipeline, "generate_note_editorial_eyecatch"), \
             patch.object(target.Image, "open", return_value=FakeImage()), \
             patch.object(target.eyecatch_contract, "upload_current_asset_pair", return_value=after["eyecatch_url"]), \
             patch.object(target.eyecatch_contract, "require_current_asset_url", return_value=after["eyecatch_url"]), \
             patch.object(target, "_patch_source_eyecatch") as mutate:
            result = target.finalize_ready_eyecatch(SYNC_ID)

        self.assertEqual(result["status"], "ready_eyecatch_finalized")
        self.assertTrue(result["body_unchanged"])
        self.assertTrue(result["title_unchanged"])
        self.assertFalse(result["article_regeneration"])
        self.assertFalse(result["note_mutation"])
        mutate.assert_called_once_with(SYNC_ID, after["eyecatch_url"], TITLE)

    def test_refuses_noncurrent_manuscript_instead_of_restamping(self):
        page = {"id": SYNC_ID}
        state = {"sync_id": SYNC_ID, "title": TITLE, "source": "HackerNews", "eyecatch_url": ""}
        with patch.dict(os.environ, {"NOTION_API_KEY": "x", "GH_PAT": "y"}, clear=False), \
             patch.object(target, "_source_page", return_value=page), \
             patch.object(target.ready_sync, "_source_state", return_value=state), \
             patch.object(target.ready_sync, "_source_current_ready_manuscript", return_value=""):
            with self.assertRaisesRegex(target.ReadyEyecatchError, "refusing to restamp"):
                target.finalize_ready_eyecatch(SYNC_ID)


if __name__ == "__main__":
    import unittest
    unittest.main()
