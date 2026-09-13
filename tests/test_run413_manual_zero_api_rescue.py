from __future__ import annotations

import inspect
import types
import unittest
from unittest.mock import patch

import run413_manual_zero_api_rescue as run413


class Run413ManualZeroApiRescueTests(unittest.TestCase):
    def _pipeline(self):
        return types.SimpleNamespace(
            build_clean_note_manuscript=lambda body, repo_name, repo_url, spdx, source, **kwargs: (
                f"# {kwargs['title_text']}\n\n"
                "## 30秒でわかるこの記事\n\n"
                f"**何が出た？**  \n{kwargs['reader_summary']['what']}\n\n"
                f"**なぜ重要？**  \n{kwargs['reader_summary']['why']}\n\n"
                f"**結論は？**  \n{kwargs['reader_summary']['decision']}\n\n"
                + body
                + f"\n\n### Sources / Evidence\n- {repo_url}"
            )
        )

    def _stored(self):
        return (
            "# 古い公開タイトル\n\n"
            "### 元情報\n- **主一次情報**: [source](https://www.rubyhack.ai/)\n- **発見経路**: Hacker News\n\n"
            "導入文です。\n\n"
            "## 技術的なポイント\n\n確認済みの挙動を説明します。\n\n"
            "## 開発リーダーが今取るべきスタンス\n\n権限を点検します。\n\n"
            "---\n\n### Sources / Evidence\n- old\n\n※旧免責。"
        )

    def test_body_repair_is_deterministic_and_adds_reservation(self):
        manuscript = run413.build_zero_api_manuscript(self._pipeline(), self._stored())
        self.assertIn(run413.RESERVATION_HEADING, manuscript)
        self.assertIn("不明です", manuscript)
        self.assertIn("確認できません", manuscript)
        self.assertIn("**何が出た？**", manuscript)
        self.assertNotIn("# 古い公開タイトル", manuscript)
        self.assertNotIn("※旧免責", manuscript)

    def test_stable_summary_has_no_run249_fragment(self):
        import run249_final_publication_surface_gate as run249
        summary = {"what": run413.WHAT, "why": run413.WHY, "decision": run413.ACTION}
        self.assertEqual(run249._summary_fragment_issues(summary), [])
        self.assertEqual(run249._unbalanced_japanese_quote_issue(run413.PUBLIC_TITLE), "")

    def test_eyecatch_routes_exactly_gemini35(self):
        calls = []
        pipeline = types.SimpleNamespace()
        pipeline._call_model_pool = lambda *args, **kwargs: (
            calls.append((args, kwargs)) or '{"headline":"AIエージェントの境界線","subheadline":"RubyGems事例から権限管理を考える"}',
            "gemini-3.5-flash",
        )
        pipeline.upload_eyecatch_to_github = lambda path, name: "https://example.test/image.png"
        with patch("editorial_eyecatch.generate_note_editorial_eyecatch") as render:
            def make_file(headline, subheadline, path, **kwargs):
                with open(path, "wb") as fh:
                    fh.write(b"x" * 10001)
            render.side_effect = make_file
            url = run413.build_eyecatch_with_gemini35(pipeline)
        self.assertEqual(url, "https://example.test/image.png")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][4], ["gemini-3.5-flash"])
        self.assertEqual(calls[0][0][2], "run413_eyecatch_copy")

    def test_eyecatch_rejects_new_number(self):
        with self.assertRaisesRegex(RuntimeError, "invented a new number"):
            run413._parse_eyecatch_json('{"headline":"999件の事件","subheadline":"権限管理を考える"}')

    def test_module_contains_no_note_publication_action(self):
        source = inspect.getsource(run413)
        self.assertNotIn("public_auto", source)
        self.assertNotIn("run_public", source)
        self.assertNotIn("NOTE_PUBLISH_ENABLED", source)
        self.assertNotIn("note.com", source)

    def test_target_is_exactly_bound(self):
        self.assertEqual(run413.TARGET_PAGE_ID, "3d9479ff-dca9-819a-814c-e4a0aeb3263f")
        self.assertEqual(run413.TARGET_NAME, "OpenAI agents carried out an undisclosed attack on RubyGems")


if __name__ == "__main__":
    unittest.main()
