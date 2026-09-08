from __future__ import annotations

import inspect
import unittest

import run297_genrec_run296_rebase as r297
import run298_genrec_inplace_refresh as r298
import run296_editorial_format_v2 as r296


class Run297TransformTests(unittest.TestCase):
    def specimen(self) -> str:
        return f"""# {r296.GENREC_SOURCE_TITLE}

## 30秒でわかるこの記事

**何が出た？**  
Netflixの推薦基盤に関する技術記事です。

**なぜ重要？**  
推薦システムの設計判断に関係します。

**結論は？**  
段階的な検証が必要です。

## 本文

監査済みの本文は変更しません。

### Sources / Evidence

- https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3

### 調査と判断の時間を減らしたい方へ

旧CTA本文。

[意思決定DBを見る](https://note.com/trendhub_biz/n/example?utm_source=note)
"""

    def test_transform_is_only_run296_reader_surface(self):
        old = self.specimen()
        new = r297.transform_genrec_manuscript(old)
        self.assertIn("## どんな内容？", new)
        self.assertNotIn("30秒でわかるこの記事", new)
        self.assertNotIn("何が出た？", new)
        self.assertIn("監査済みの本文は変更しません。", new)
        self.assertIn("### 有料サブスクのご案内", new)
        self.assertIn("[詳しくはこちら](https://note.com/trendhub_biz/n/example?utm_source=note)", new)
        self.assertLess(new.index("### Sources / Evidence"), new.index("### 有料サブスクのご案内"))

    def test_exact_specimen_and_policy_are_pinned(self):
        self.assertEqual(r297.TARGET_SYNC_ID, "3bd479ffdca9817f926aeaffbb779c4b")
        self.assertEqual(
            r297.PRE_RUN296_POLICY_SHA256,
            "b1b4d1e9d5e52788dc16396480ca0b7097701dc9354d91fd299394296fd1cd45",
        )
        self.assertEqual(
            r296.GENREC_EYECATCH_LINES,
            ("Netflix推薦の舞台裏", "LLMネイティブへ", "舵を切った理由"),
        )

    def test_run297_has_no_note_browser_or_model_surface(self):
        source = inspect.getsource(r297)
        self.assertNotIn("note.com/new", source)
        self.assertNotIn("_create_browser_draft", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)


class Run298InPlaceTests(unittest.TestCase):
    def test_only_existing_editor_routes_are_accepted(self):
        self.assertEqual(
            r298._route_key("https://editor.note.com/notes/abc123/edit"),
            "/notes/abc123/edit",
        )
        self.assertEqual(r298._route_key("https://note.com/new"), "")
        self.assertEqual(r298._route_key("https://note.com/notes/abc123"), "")
        self.assertEqual(r298._route_key("https://note.com/notes/abc123/publish"), "")

    def test_run298_is_exact_target_and_has_no_new_draft_call(self):
        self.assertEqual(r298.TARGET_SYNC_ID, r297.TARGET_SYNC_ID)
        source = inspect.getsource(r298)
        self.assertNotIn("_create_browser_draft(", source)
        self.assertNotIn("NOTE_NEW_URL", source)
        self.assertNotIn("https://note.com/new", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)

    def test_surface_markers_encode_requested_final_audit(self):
        actual = (
            "どんな内容？ なぜ重要？ 結論は？ "
            "Sources / Evidence "
            f"{r296.CTA_HEADING} {r296.CTA_BODY} {r296.CTA_LINK_LABEL}"
        )
        markers = r298._new_surface_markers(actual, r296.GENREC_SOURCE_TITLE)
        self.assertTrue(markers["new_intro_present"])
        self.assertTrue(markers["old_intro_absent"])
        self.assertTrue(markers["what_row_absent"])
        self.assertTrue(markers["new_cta_heading_present"])
        self.assertTrue(markers["new_cta_body_present"])
        self.assertTrue(markers["cta_link_label_present"])
        self.assertTrue(markers["sources_before_cta"])
        self.assertFalse(markers["duplicate_title_prefix"])


if __name__ == "__main__":
    unittest.main()
