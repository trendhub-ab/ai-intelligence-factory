import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import subscriber_decision_brief as sdb


def resp(status=200, data=None, text="", headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data or {}
    r.text = text
    r.headers = headers or {}
    return r


def rt(v):
    return {"rich_text": [{"plain_text": v, "text": {"content": v}}]} if v else {"rich_text": []}


def title(v):
    return {"title": [{"plain_text": v, "text": {"content": v}}]} if v else {"title": []}


def sel(v):
    return {"select": {"name": v}} if v else {"select": None}


def date(v):
    return {"date": {"start": v}} if v else {"date": None}


def subscriber_page(page_id="p1"):
    return {
        "id": page_id,
        "properties": {
            "技術・プロジェクト名": title("mlflow/mlflow"),
            "日本語表示名": rt("MLflow — 判断用レビュー"),
            "分野（内部）": sel("DEVTOOLS"),
            "採用スコア（内部）": {"number": 94},
            "採用判断（内部）": sel("ADOPT"),
            "実用準備度（内部）": sel("HIGH"),
            "根拠信頼度（内部）": sel("HIGH"),
            "わかりやすい要約（内部）": rt("AI・機械学習の実験、評価、モデルやプロンプト管理をまとめて行う基盤。"),
            "今回の話題（内部）": rt("LLMやAIエージェントのトレーシング、評価、プロンプト管理まで用途が広がった。"),
            "判断理由（内部）": rt("実験追跡からLLM運用まで一元管理できるため。"),
            "向いている用途（内部）": rt("LLM・AIエージェントを継続運用する開発チーム。"),
            "向いていない用途（内部）": rt("管理機能が不要な単発スクリプト。"),
            "主リスク（内部）": rt("セルフホスト時のサーバー維持と権限管理。"),
            "公式URL": {"url": "https://github.com/mlflow/mlflow"},
            "一次情報URL（内部）": rt("https://github.com/mlflow/mlflow\nhttps://mlflow.org"),
            "最終レビュー日（内部）": date("2026-08-29T00:00:00+00:00"),
        },
    }


def managed_toggle(block_id="t1"):
    return {
        "id": block_id,
        "type": "toggle",
        "toggle": {"rich_text": [{"plain_text": sdb.AUTO_MARKER, "text": {"content": sdb.AUTO_MARKER}}]},
    }


class Run158DecisionBriefTests(unittest.TestCase):
    def test_page_parser_uses_only_existing_subscriber_properties(self):
        values = sdb.page_to_values(subscriber_page())
        self.assertEqual(values["name"], "mlflow/mlflow")
        self.assertEqual(values["adoption_score"], 94)
        self.assertEqual(values["plain_summary"], "AI・機械学習の実験、評価、モデルやプロンプト管理をまとめて行う基盤。")
        self.assertEqual(values["evidence_urls"], ["https://github.com/mlflow/mlflow", "https://mlflow.org"])

    def test_brief_contains_decision_and_product_sections(self):
        values = sdb.page_to_values(subscriber_page())
        toggle = sdb.build_decision_brief_toggle(values)
        self.assertEqual(toggle["type"], "toggle")
        self.assertEqual(toggle["toggle"]["rich_text"][0]["text"]["content"], sdb.AUTO_MARKER)
        rendered = str(toggle)
        for expected in ["ADOPT", "94/100", "これは何？", "向いている用途", "向いていない用途", "主なリスク", "一次情報"]:
            self.assertIn(expected, rendered)

    def test_status_language_does_not_invent_new_facts(self):
        self.assertIn("限定検証", sdb._status_conclusion("TEST"))
        self.assertIn("継続監視", sdb._status_conclusion("WATCH"))
        self.assertIn("新規採用を見送る", sdb._status_conclusion("AVOID"))

    def test_notion_request_honors_json_retry_after_and_recovers(self):
        old_pacing = sdb.REQUEST_PACING_SECONDS
        old_attempts = sdb.REQUEST_MAX_ATTEMPTS
        sdb.REQUEST_PACING_SECONDS = 0.0
        sdb.REQUEST_MAX_ATTEMPTS = 3
        try:
            limited = resp(
                429,
                {"additional_data": {"retry_after": "2.5"}},
                text="rate limited",
            )
            ok = resp(200, {"results": []})
            with patch.object(sdb.requests, "get", side_effect=[limited, ok]) as get, patch.object(sdb.time, "sleep") as sleep:
                result = sdb._request("GET", "https://api.notion.com/v1/blocks/test/children")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(get.call_count, 2)
            sleep.assert_called_once_with(2.5)
        finally:
            sdb.REQUEST_PACING_SECONDS = old_pacing
            sdb.REQUEST_MAX_ATTEMPTS = old_attempts

    def test_notion_request_prefers_retry_after_header_and_caps_delay(self):
        old_pacing = sdb.REQUEST_PACING_SECONDS
        old_attempts = sdb.REQUEST_MAX_ATTEMPTS
        old_cap = sdb.RETRY_AFTER_MAX_SECONDS
        sdb.REQUEST_PACING_SECONDS = 0.0
        sdb.REQUEST_MAX_ATTEMPTS = 3
        sdb.RETRY_AFTER_MAX_SECONDS = 10.0
        try:
            limited = resp(
                429,
                {"additional_data": {"retry_after": "3"}},
                headers={"Retry-After": "99"},
            )
            ok = resp(200, {"results": []})
            with patch.object(sdb.requests, "get", side_effect=[limited, ok]), patch.object(sdb.time, "sleep") as sleep:
                result = sdb._request("GET", "https://api.notion.com/v1/blocks/test/children")
            self.assertEqual(result.status_code, 200)
            sleep.assert_called_once_with(10.0)
        finally:
            sdb.REQUEST_PACING_SECONDS = old_pacing
            sdb.REQUEST_MAX_ATTEMPTS = old_attempts
            sdb.RETRY_AFTER_MAX_SECONDS = old_cap

    def test_notion_request_retries_transient_5xx_then_succeeds(self):
        old_pacing = sdb.REQUEST_PACING_SECONDS
        old_attempts = sdb.REQUEST_MAX_ATTEMPTS
        sdb.REQUEST_PACING_SECONDS = 0.0
        sdb.REQUEST_MAX_ATTEMPTS = 3
        try:
            with patch.object(sdb.requests, "post", side_effect=[resp(503), resp(200, {"results": []})]) as post, patch.object(sdb.time, "sleep") as sleep:
                result = sdb._request("POST", "https://api.notion.com/v1/data_sources/test/query", json_payload={"page_size": 100})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(post.call_count, 2)
            sleep.assert_called_once_with(1.0)
        finally:
            sdb.REQUEST_PACING_SECONDS = old_pacing
            sdb.REQUEST_MAX_ATTEMPTS = old_attempts

    def test_notion_request_paces_each_successful_transport_call(self):
        old_pacing = sdb.REQUEST_PACING_SECONDS
        sdb.REQUEST_PACING_SECONDS = 0.4
        try:
            with patch.object(sdb.requests, "get", return_value=resp(200, {"results": []})), patch.object(sdb.time, "sleep") as sleep:
                result = sdb._request("GET", "https://api.notion.com/v1/blocks/test/children")
            self.assertEqual(result.status_code, 200)
            sleep.assert_called_once_with(0.4)
        finally:
            sdb.REQUEST_PACING_SECONDS = old_pacing

    def test_no_managed_block_appends_without_deleting_manual_content(self):
        values = sdb.page_to_values(subscriber_page())
        manual = {"id": "manual1", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "manual"}]}}
        with patch.object(sdb, "_list_children", return_value=[manual]), patch.object(sdb, "_append_toggle", return_value="new1") as append, patch.object(sdb, "_delete_block") as delete:
            state = sdb.sync_page(values)
        self.assertEqual(state, "created")
        append.assert_called_once()
        delete.assert_not_called()

    def test_full_brief_signature_is_idempotent(self):
        values = sdb.page_to_values(subscriber_page())
        current_children = sdb.build_decision_brief_toggle(values)["toggle"]["children"]
        with patch.object(sdb, "_list_children", side_effect=[[managed_toggle()], current_children]), patch.object(sdb, "_append_toggle") as append, patch.object(sdb, "_delete_block") as delete:
            state = sdb.sync_page(values)
        self.assertEqual(state, "unchanged")
        append.assert_not_called()
        delete.assert_not_called()

    def test_risk_only_change_refreshes_brief_even_when_decision_key_is_same(self):
        old_values = sdb.page_to_values(subscriber_page())
        current_children = sdb.build_decision_brief_toggle(old_values)["toggle"]["children"]
        new_values = dict(old_values)
        new_values["main_risk"] = "新しい運用リスクが一次情報で確認された。"
        self.assertEqual(sdb.decision_key(old_values), sdb.decision_key(new_values))
        with patch.object(sdb, "_list_children", side_effect=[[managed_toggle("old1")], current_children]), patch.object(sdb, "_append_toggle", return_value="new1") as append, patch.object(sdb, "_delete_block") as delete, patch.object(sdb, "_sleep"):
            state = sdb.sync_page(new_values)
        self.assertEqual(state, "updated")
        append.assert_called_once()
        delete.assert_called_once_with("old1")

    def test_stale_auto_block_is_replaced_content_first(self):
        values = sdb.page_to_values(subscriber_page())
        stale = [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "OLD"}]}}]
        with patch.object(sdb, "_list_children", side_effect=[[managed_toggle("old1")], stale]), patch.object(sdb, "_append_toggle", return_value="new1") as append, patch.object(sdb, "_delete_block") as delete, patch.object(sdb, "_sleep"):
            state = sdb.sync_page(values)
        self.assertEqual(state, "updated")
        append.assert_called_once()
        delete.assert_called_once_with("old1")

    def test_database_sync_runs_when_brief_enabled_even_without_property_sync_flag(self):
        old_brief, old_key = sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF, sdb.NOTION_API_KEY
        sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF = True
        sdb.NOTION_API_KEY = "x"
        try:
            with patch.object(sdb, "query_subscriber_pages", return_value=[subscriber_page("p1")]), patch.object(sdb, "sync_page", return_value="created") as sync:
                result = sdb.sync_subscriber_decision_briefs()
            self.assertTrue(result["enabled"])
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["created"], 1)
            sync.assert_called_once()
        finally:
            sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF, sdb.NOTION_API_KEY = old_brief, old_key

    def test_database_sync_fails_closed_on_partial_error(self):
        old_brief, old_key = sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF, sdb.NOTION_API_KEY
        sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF = True
        sdb.NOTION_API_KEY = "x"
        try:
            with patch.object(sdb, "query_subscriber_pages", return_value=[subscriber_page("p1"), subscriber_page("p2")]), patch.object(sdb, "sync_page", side_effect=["created", RuntimeError("boom")]):
                with self.assertRaises(RuntimeError):
                    sdb.sync_subscriber_decision_briefs()
        finally:
            sdb.ENABLE_SUBSCRIBER_DECISION_BRIEF, sdb.NOTION_API_KEY = old_brief, old_key


if __name__ == "__main__":
    unittest.main(verbosity=2)