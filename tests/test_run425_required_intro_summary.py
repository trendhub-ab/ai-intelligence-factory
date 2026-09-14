import unittest
from types import SimpleNamespace

import run425_required_intro_summary as r425


class Run425RequiredIntroSummaryTests(unittest.TestCase):
    def _projection(self, what="何が起きたかを説明する十分な要約です。", why="なぜ実務上重要なのかを説明する十分な要約です。", decision="まず権限と外部通信を点検し、今後の一次情報を追います。"):
        return f"""# 記事タイトル

## どんな内容？

{what}

**なぜ重要？**
{why}

**結論は？**
{decision}

### 元情報
- source
"""

    def test_complete_reader_intro_passes_contract(self):
        summary = {
            "what": "何が起きたかを説明する十分な要約です。",
            "why": "なぜ実務上重要なのかを説明する十分な要約です。",
            "decision": "まず権限と外部通信を点検し、今後の一次情報を追います。",
        }
        self.assertEqual(r425.summary_contract_issues(summary, self._projection()), [])

    def test_missing_any_answer_fails_closed(self):
        summary = {"what": "十分な内容説明があります。", "why": "十分な重要性説明があります。", "decision": ""}
        issues = r425.summary_contract_issues(summary, self._projection(decision=""))
        self.assertTrue(any("final_surface_summary_missing:結論は？" in x for x in issues))

    def test_wrong_order_and_legacy_what_label_are_rejected(self):
        projection = """# title

## どんな内容？
十分な内容説明です。

**何が出た？**
古いラベルです。

**結論は？**
十分な結論です。

**なぜ重要？**
十分な重要性説明です。
"""
        summary = {"what": "十分な内容説明です。", "why": "十分な重要性説明です。", "decision": "十分な結論です。"}
        issues = r425.summary_contract_issues(summary, projection)
        self.assertTrue(any("legacy_what_label_present" in x for x in issues))
        self.assertTrue(any("intro_order_invalid" in x for x in issues))

    def test_install_forces_weak_without_relaxing_existing_issues(self):
        summary = {"what": "十分な内容説明があります。", "why": "十分な重要性説明があります。", "decision": ""}

        def human(_parsed, _peer=None):
            return "ACCEPTABLE", ["existing_issue"]

        def build_summary(_parsed):
            return dict(summary)

        def build_manuscript(_article, _source_title, *_args, reader_summary=None, title_text="", **_kwargs):
            s = reader_summary or {}
            return self._projection(
                what=s.get("what", ""),
                why=s.get("why", ""),
                decision=s.get("decision", ""),
            )

        p = SimpleNamespace(
            validate_human_appeal_gate=human,
            build_reader_first_summary=build_summary,
            build_clean_note_manuscript=build_manuscript,
        )
        r425.install(p)
        state, issues = p.validate_human_appeal_gate({"title_text": "title", "note_draft": "body"})
        self.assertEqual(state, "WEAK")
        self.assertIn("existing_issue", issues)
        self.assertTrue(any("final_surface_summary_missing:結論は？" in x for x in issues))
        self.assertTrue(p.RUN425_ZERO_PROVIDER_CALLS)

    def test_run425_has_no_generation_or_publish_surface(self):
        source = open(r425.__file__, encoding="utf-8").read().lower()
        for forbidden in ("generate_content(", "_generate_via_chat(", "publish_note", "click_publish", "requests.post("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
