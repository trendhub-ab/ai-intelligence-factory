from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import current_policy_ready_recovery as recovery
import production_pipeline

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "current-policy-ready-recovery.yml"


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _rt(value):
    return {"rich_text": [{"plain_text": value, "text": {"content": value}}]}


def _title(value):
    return {"title": [{"plain_text": value, "text": {"content": value}}]}


def _page(page_id, *, source="GitHub", article_value=80, decision_score=80, screening=70, name=None):
    return {
        "id": page_id,
        "properties": {
            "Name": _title(name or page_id),
            "URL": {"url": f"https://example.com/{page_id}"},
            "Source": {"select": {"name": source}},
            "Content Status": {"select": {"name": "Deep Dive"}},
            "Article Status": {"select": {"name": "Ready"}},
            "License": _rt("MIT" if source == "GitHub" else "N/A"),
            "Engagement": {"number": 10},
            "Published At": {"date": {"start": "2026-09-01T00:00:00Z"}},
            "Analyzed At": {"date": {"start": "2026-09-07T00:00:00Z"}},
            "Screening Score": {"number": screening},
            "Screening Reason": _rt("persisted screening"),
            "Article Value": {"number": article_value},
            "Decision Score": {"number": decision_score},
            "Summary": _rt("persisted summary"),
        },
    }


def _selector_pipeline(rows, block_bodies):
    class _Requests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            if "/blocks/" in url:
                page_id = url.split("/blocks/", 1)[1].split("/", 1)[0]
                body = block_bodies.get(page_id, "old")
                return _Response({
                    "results": [{
                        "type": "code",
                        "code": {
                            "rich_text": [{"plain_text": body}],
                            "caption": [{"plain_text": "caption"}],
                        },
                    }],
                    "has_more": False,
                })
            raise AssertionError(f"unexpected GET {url}")

    return SimpleNamespace(
        requests=_Requests,
        logger=_Logger(),
        NOTION_API_KEY="token",
        _notion_headers=lambda: {"Authorization": "test"},
        _notion_query_url=lambda: "https://api.notion.com/v1/data_sources/test/query",
        _query_notion_db_with_retry=lambda url, headers, payload: _Response({"results": rows}),
        _notion_plain_text=lambda prop: "".join(
            x.get("plain_text") or x.get("text", {}).get("content", "")
            for x in (prop.get("title") or prop.get("rich_text") or [])
        ),
        legal_safety_gate=lambda repo: (True, "SAFE"),
        PROP_NAME="Name",
        PROP_URL="URL",
        PROP_SOURCE="Source",
        PROP_CONTENT_STATUS="Content Status",
        PROP_ARTICLE_STATUS="Article Status",
        PROP_LICENSE="License",
        PROP_ENGAGEMENT="Engagement",
        PROP_PUBLISHED_AT="Published At",
        PROP_ANALYZED_AT="Analyzed At",
        PROP_SCREENING_SCORE="Screening Score",
        PROP_SCREENING_REASON="Screening Reason",
        PROP_ARTICLE_VALUE="Article Value",
        PROP_SCORE="Decision Score",
        PROP_SOURCE_SUMMARY="Summary",
        CONTENT_STATUS_DEEP_DIVE="Deep Dive",
        ARTICLE_STATUS_READY="Ready",
    )


class Run282SelectionTests(unittest.TestCase):
    def test_selects_highest_business_value_stale_ready_and_excludes_retired_source(self):
        rows = [
            _page("current-top", article_value=100, decision_score=100),
            _page("stale-low", article_value=80, decision_score=95),
            _page("stale-high", article_value=95, decision_score=70),
            _page("retired-ph", source="ProductHunt", article_value=100, decision_score=100),
        ]
        pipeline = _selector_pipeline(rows, {"current-top": "current", "stale-low": "old", "stale-high": "old"})
        with mock.patch.object(
            recovery.publication_contract,
            "is_current_ready_block",
            side_effect=lambda body, caption: body == "current",
        ):
            selected = recovery.select_stale_ready_items(pipeline, limit=1)
        self.assertEqual([row["notion_page_id"] for row in selected], ["stale-high"])
        self.assertEqual(selected[0]["article_value"], 95.0)
        self.assertEqual(selected[0]["repo"]["source"], "GitHub")

    def test_block_read_uncertainty_never_becomes_stale(self):
        rows = [_page("candidate", article_value=99)]
        pipeline = _selector_pipeline(rows, {})
        with mock.patch.object(recovery, "_has_current_ready_manuscript", return_value=None):
            self.assertEqual(recovery.select_stale_ready_items(pipeline, limit=1), [])


class Run282ExecutionTests(unittest.TestCase):
    def _pipeline(self, generated_status="accepted", generated_value="body"):
        calls = []

        class DailyQuotaExhaustedError(Exception):
            pass

        def generate(repo, **kwargs):
            calls.append((repo, kwargs))
            if generated_value is None:
                return None
            return (generated_value, generated_status)

        pipeline = SimpleNamespace(
            logger=_Logger(),
            DEEP_DIVE_MODEL_BUDGET=SimpleNamespace(budget=12),
            ARTICLE_STATUS_READY="Ready",
            DailyQuotaExhaustedError=DailyQuotaExhaustedError,
            generate_intelligence_report=generate,
        )
        return pipeline, calls

    def test_recovery_is_one_row_persistent_and_verified_from_notion(self):
        pipeline, calls = self._pipeline("accepted")
        item = {
            "notion_page_id": "page-1",
            "screening_score": 90,
            "screening_reason": "high value",
            "article_value": 98,
            "decision_score": 91,
            "repo": {"nameWithOwner": "vendor/project", "source": "OfficialVendor"},
        }
        with mock.patch.object(recovery, "select_stale_ready_items", return_value=[item]), \
             mock.patch.object(recovery, "_read_article_status", return_value="Ready"), \
             mock.patch.object(recovery, "_has_current_ready_manuscript", return_value=True), \
             mock.patch.dict(os.environ, {
                 "CURRENT_POLICY_READY_RECOVERY_LIMIT": "9",
                 "CURRENT_POLICY_READY_RECOVERY_REQUEST_BUDGET": "99",
             }, clear=False):
            result = recovery.run_current_policy_ready_recovery(pipeline)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["persisted_status_counts"], {"Ready": 1})
        self.assertEqual(result["recovered"], 1)
        self.assertEqual(pipeline.DEEP_DIVE_MODEL_BUDGET.budget, 4)
        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertTrue(kwargs["persist_results"])
        self.assertEqual(kwargs["notion_page_id"], "page-1")
        self.assertEqual(kwargs["candidate_origin"], "current_policy_ready_recovery")
        self.assertIs(kwargs["attribution_context"], item)

    def test_rejected_generation_is_never_counted_recovered_or_forced_ready(self):
        pipeline, _calls = self._pipeline("rejected")
        item = {
            "notion_page_id": "page-2",
            "screening_score": 85,
            "screening_reason": "candidate",
            "article_value": 90,
            "decision_score": 90,
            "repo": {"nameWithOwner": "repo/two", "source": "GitHub"},
        }
        with mock.patch.object(recovery, "select_stale_ready_items", return_value=[item]), \
             mock.patch.object(recovery, "_read_article_status", return_value="Needs Editorial Review") as status_read, \
             mock.patch.object(recovery, "_has_current_ready_manuscript") as current_read:
            result = recovery.run_current_policy_ready_recovery(pipeline, limit=1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["persisted_status_counts"], {"Needs Editorial Review": 1})
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["recovered"], 0)
        status_read.assert_called_once_with(pipeline, "page-2")
        current_read.assert_not_called()

    def test_falsy_generation_reports_persisted_pending_retry_without_claiming_generated(self):
        pipeline, calls = self._pipeline(generated_value=None)
        item = {
            "notion_page_id": "page-firefox",
            "screening_score": 85,
            "screening_reason": "candidate",
            "article_value": 90,
            "decision_score": 85,
            "repo": {"nameWithOwner": "Firefox candidate", "source": "HackerNews"},
        }
        with mock.patch.object(recovery, "select_stale_ready_items", return_value=[item]), \
             mock.patch.object(recovery, "_read_article_status", return_value="Pending Retry"), \
             mock.patch.object(recovery, "_has_current_ready_manuscript") as current_read:
            result = recovery.run_current_policy_ready_recovery(pipeline, limit=1)

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["generated"], 0)
        self.assertEqual(result["persisted_status_counts"], {"Pending Retry": 1})
        self.assertEqual(result["recovered"], 0)
        current_read.assert_not_called()

    def test_dispatch_mode_can_select_recovery_without_daily(self):
        with mock.patch.dict(os.environ, {"AIIF_ONE_SHOT_MODE": "current_policy_ready_recovery"}, clear=False):
            self.assertEqual(production_pipeline._workflow_dispatch_mode(), "current_policy_ready_recovery")


class Run282WorkflowTests(unittest.TestCase):
    def test_dedicated_workflow_is_manual_bounded_zero_vm_and_fail_closed_on_zero_ready(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertIn("RECOVER_ONE_READY", text)
        self.assertIn("AIIF_ONE_SHOT_MODE: 'current_policy_ready_recovery'", text)
        self.assertIn("CURRENT_POLICY_READY_RECOVERY_LIMIT: '1'", text)
        self.assertIn("CURRENT_POLICY_READY_RECOVERY_REQUEST_BUDGET: '4'", text)
        self.assertIn("GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET: '4'", text)
        self.assertIn("python note_ready_sync.py", text)
        self.assertIn("current-policy source_ready stayed 0", text)
        self.assertIn("RUN282_CURRENT_POLICY_READY_VERIFIED", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("playwright", text.lower())
        self.assertNotIn("note.com", text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
