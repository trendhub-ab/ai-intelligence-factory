import json
import tempfile
import unittest
from pathlib import Path

from ai_provider import GenerationRequest, GroqProvider
from groq_two_pass_article import (
    TwoPassArticleError,
    assemble_combined_report,
    build_plan_fixture,
    build_writer_fixture,
    parse_writer_report,
    validate_plan,
)


FIXTURE = "tests/fixtures/groq/article_parity_B0049_input.json"


def valid_plan():
    return {
        "source_summary": "AstraはCritical級サイバー能力の閾値に到達した。",
        "what": "限定条件下のサイバー評価で高い能力が報告された。",
        "why_important": "能力と公開条件を分けて判断する必要がある。",
        "decision": "WATCH",
        "decision_reason": ["能力は確認された", "一般利用条件は確認できない"],
        "business_impact": 10,
        "technical_impact": 16,
        "urgency": 10,
        "market_impact": 8,
        "reliability": 12,
        "action": "利用条件と安全策の一次情報を確認する。",
        "article_value": 78,
        "article_angle": "100%という数字より、その数字がどの条件で出たかに注目する。",
        "reader_bridge": "簡単に言えば、強さの数字と実際に使える条件は別の話です。",
        "title_seed": "100%の向こう側にある利用条件",
        "access_status": "NOT_CONFIRMED",
    }


def report(model, text, prompt_tokens=100, completion_tokens=100):
    return {
        "provider": "groq", "model": model, "provider_calls": 1, "business_writes": 0,
        "result": {"text": text, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


class GroqTwoPassArticleTests(unittest.TestCase):
    def test_plan_fixture_fits_standalone_free_plan(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "plan-fixture.json"
            fixture = build_plan_fixture(FIXTURE, str(out))
            self.assertEqual(fixture["model"], "openai/gpt-oss-120b")
            self.assertEqual(fixture["rate_policy"], "gpt_oss_120b")
            self.assertIsNotNone(fixture["schema"])
            provider = GroqProvider(
                lambda _: None,
                validate_schema=lambda data, schema: None,
                token_budget=7000,
                model=fixture["model"],
            )
            payload, estimate = provider.prepare(GenerationRequest(
                fixture["prompt"], fixture["max_output_tokens"], fixture["schema"], fixture["reasoning_effort"]
            ))
            self.assertLessEqual(estimate, 7000)
            self.assertEqual(payload["response_format"]["type"], "json_schema")
            self.assertEqual(fixture["business_writes"], 0)

    def test_unconfirmed_access_cannot_escalate_to_poc(self):
        plan = valid_plan()
        plan["action"] = "Daybreak Blueを申請してPoCを実施する。"
        with self.assertRaisesRegex(TwoPassArticleError, "unconfirmed_access_action_escalation"):
            validate_plan(plan)

    def test_writer_fixture_is_article_only_and_compound(self):
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text(json.dumps(report("openai/gpt-oss-120b", json.dumps(valid_plan(), ensure_ascii=False))), encoding="utf-8")
            out = Path(td) / "writer-fixture.json"
            fixture = build_writer_fixture(FIXTURE, str(plan_path), str(out))
            self.assertEqual(fixture["model"], "groq/compound-mini")
            self.assertEqual(fixture["rate_policy"], "compound_mini_article")
            self.assertNotIn("=== MANAGEMENT DATA ===", fixture["prompt"])
            self.assertIn("Markdownの箇条書き・番号リストは禁止", fixture["prompt"])
            self.assertIn("ALLOWED FACT LEDGER", fixture["prompt"])
            self.assertIn("access_status", fixture["prompt"])
            provider = GroqProvider(lambda _: None, token_budget=60000, model=fixture["model"])
            payload, estimate = provider.prepare(GenerationRequest(
                fixture["prompt"], fixture["max_output_tokens"], None, fixture["reasoning_effort"]
            ))
            self.assertLessEqual(estimate, 60000)
            self.assertEqual(payload["compound_custom"]["tools"]["enabled_tools"], [])

    def test_writer_rejects_list_output(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "writer.json"
            path.write_text(json.dumps(report(
                "groq/compound-mini",
                "===TITLE===\nタイトルです。\n===ARTICLE===\n" + ("本文です。" * 180) + "\n- 箇条書き"
            ), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(TwoPassArticleError, "writer_list_output_forbidden"):
                parse_writer_report(str(path))

    def test_two_pass_assembly_restores_production_parser_surface(self):
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            writer_path = Path(td) / "writer.json"
            combined_path = Path(td) / "combined.json"
            plan_path.write_text(json.dumps(report(
                "openai/gpt-oss-120b", json.dumps(valid_plan(), ensure_ascii=False), 200, 300
            ), ensure_ascii=False), encoding="utf-8")
            article = "簡単に言えば、この100%は何でもできるという意味ではありません。" + ("条件を分けて読むことが大切です。" * 80)
            writer_path.write_text(json.dumps(report(
                "groq/compound-mini", "===TITLE===\n100%という数字を、そのまま信じてよい？\n===ARTICLE===\n" + article, 400, 500
            ), ensure_ascii=False), encoding="utf-8")
            combined = assemble_combined_report(str(plan_path), str(writer_path), str(combined_path))
            self.assertEqual(combined["provider_calls"], 2)
            self.assertEqual(combined["business_writes"], 0)
            self.assertEqual(combined["result"]["prompt_tokens"], 600)
            self.assertEqual(combined["result"]["completion_tokens"], 800)
            text = combined["result"]["text"]
            self.assertIn("=== MANAGEMENT DATA ===", text)
            self.assertIn("===SECTION_SPLIT_TOKEN===", text)
            self.assertIn("===NOTE_DRAFT_START===", text)
            self.assertIn("・Decision: WATCH", text)
            self.assertIn("合計 56/100", text)
            self.assertIn("100%という数字を、そのまま信じてよい？", text)


if __name__ == "__main__":
    unittest.main()
