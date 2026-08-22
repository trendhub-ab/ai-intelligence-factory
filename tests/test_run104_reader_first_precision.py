import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")
import pipeline


class Run104ReaderFirstPrecisionTests(unittest.TestCase):
    def test_jargon_heavy_what_prefers_plain_existing_source_summary(self):
        parsed = {
            "note_draft": "## 現場の困りごとから\nMCPの次期ロードマップが公開されました。",
            "what_text": (
                "MCPの将来的な機能拡張と標準化の方針が策定され、タスク管理（SEP-2663）、"
                "DPoPやWorkload Identity Federation、Progressive Discoveryなどが提示された。"
            ),
            "source_summary_text": "MCPの次期ロードマップが公開され、今後の重点領域が示されました。",
            "why_important_text": "実務上の課題に関係します。",
            "decision_reason_text": "動向を確認します。",
        }
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertIn(summary["what"], {
            "MCPの次期ロードマップが公開されました。",
            "MCPの次期ロードマップが公開され、今後の重点領域が示されました。",
        })
        self.assertNotIn("SEP-2663", summary["what"])
        self.assertNotIn("Workload Identity Federation", summary["what"])

    def test_reader_body_deduplicates_source_and_early_conclusion_but_keeps_final_judgment(self):
        draft = (
            "## 現場の困りごとから\n"
            "背景です。\n\n"
            "本記事は、公式ブログの一次情報に基づいています。\n\n"
            "## 先に判断を書くと。\n"
            "全面刷新は不要です。\n\n"
            "## 今回の仕組みを見てみる。\n"
            "仕組みを説明します。\n\n"
            "### 結論として、いま取る距離感。\n"
            "小規模検証が妥当です。"
        )
        cleaned = pipeline._prepare_reader_first_body(draft, {"decision": "小規模検証が妥当です。"})
        self.assertNotIn("本記事は、公式ブログの一次情報に基づいています。", cleaned)
        self.assertNotIn("## 先に判断を書くと。", cleaned)
        self.assertIn("### 結論として、いま取る距離感。", cleaned)
        self.assertIn("小規模検証が妥当です。", cleaned)

    def test_coming_months_cannot_be_expanded_to_half_year_without_evidence(self):
        failures = pipeline._find_unsupported_numeric_claims(
            "今後数ヶ月から半年の間に仕様が進む。",
            "The working groups will continue this work over the coming months.",
        )
        self.assertFalse(any("数ヶ月" in row for row in failures), failures)
        self.assertTrue(any("半年" in row for row in failures), failures)

    def test_production_audit_reset_removes_stale_ready_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "article_audit"
            stale = root / "articles" / "ready" / "octo_example" / "final.md"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("test residue", encoding="utf-8")
            with patch.object(pipeline, "ARTICLE_AUDIT_DIR", str(root)):
                pipeline.reset_article_audit_for_production_run()
            self.assertTrue(root.exists())
            self.assertEqual([], list(root.rglob("*.md")))


if __name__ == "__main__":
    unittest.main()
