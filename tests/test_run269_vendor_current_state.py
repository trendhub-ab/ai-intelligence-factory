from __future__ import annotations

import unittest

from run269_vendor_current_state import (
    OFFICIAL_VENDOR_REGISTRY,
    _VOLCENGINE_DOC_FETCH_API,
    _extract_recent_update,
    _has_model_list_current_state,
    fetch_official_vendor_updates,
)
from source_normalization import normalize_item


class FakeResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class FakeJsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class Run269VendorCurrentStateTests(unittest.TestCase):
    def _vendor(self):
        return {
            "vendor": "ByteDance Doubao/Seed",
            "region": "CN",
            "release_url": "https://example.com/models?lang=zh",
            "allowed_domains": ("example.com",),
            "current_state_page": True,
            "current_state_label": "公式モデル一覧",
        }

    def test_bytedance_registry_uses_official_model_list_current_state(self):
        row = next(row for row in OFFICIAL_VENDOR_REGISTRY if row["vendor"] == "ByteDance Doubao/Seed")
        self.assertTrue(row["current_state_page"])
        self.assertIn("1799865", row["release_url"])
        self.assertIn("1330310", row["current_state_fetch_url"])

    def test_minimax_registry_accepts_only_known_official_domain_families(self):
        row = next(row for row in OFFICIAL_VENDOR_REGISTRY if row["vendor"] == "MiniMax")
        allowed = tuple(row["allowed_domains"])
        self.assertIn("platform.minimaxi.com", allowed)
        self.assertIn("minimaxi.com", allowed)
        self.assertIn("platform.minimax.cn", allowed)
        self.assertIn("minimax.cn", allowed)
        self.assertNotIn("minimax.com", allowed)

    def test_minimax_official_cn_redirect_is_accepted(self):
        vendor = next(row for row in OFFICIAL_VENDOR_REGISTRY if row["vendor"] == "MiniMax")
        html = (
            '<h1>Release notes</h1><h2>Sep 10, 2026</h2>'
            '<h3>MiniMax M3 model update</h3><p>MiniMax M3 model released for API use.</p>'
        )
        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(
                html,
                "https://platform.minimax.cn/docs/release-notes/models",
            ),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["sourceDetails"]["vendor_record_kind"].startswith("structured_"))

    def test_recent_update_timestamp_is_extracted_from_official_page_shape(self):
        self.assertEqual(
            "2026.07.20",
            _extract_recent_update("<div>模型列表</div><span>最近更新时间：2026.07.20 17:28:20</span>"),
        )

    def test_model_list_markers_are_specific_enough_for_current_state(self):
        self.assertTrue(_has_model_list_current_state("<h1>模型列表</h1><a>最新模型：Seed-Evolving</a>"))
        self.assertFalse(_has_model_list_current_state("<h1>模型列表</h1><p>文档中心</p>"))
        self.assertFalse(_has_model_list_current_state("<h1>产品文档</h1><p>Seed-Evolving</p>"))

    def test_timestamp_fallback_becomes_explicit_structured_current_state(self):
        vendor = self._vendor()
        html = "<h1>模型列表</h1><p>最近更新时间：2026.07.20 17:28:20</p>"

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        details = rows[0]["sourceDetails"]
        self.assertEqual("structured_current_state", details["vendor_record_kind"])
        self.assertTrue(details["current_state_page"])
        self.assertTrue(details["current_state_timestamp_observed"])
        self.assertEqual("2026.07.20", rows[0]["publishedAt"])
        self.assertIn("リリースイベントではなく", rows[0]["sourceContext"])

    def test_model_markers_without_timestamp_are_structured_but_date_is_not_fabricated(self):
        vendor = self._vendor()
        html = "<h1>模型列表</h1><a>最新模型：Seed-Evolving</a><p>Doubao Seedance 2.0</p>"

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        details = rows[0]["sourceDetails"]
        self.assertEqual("structured_current_state", details["vendor_record_kind"])
        self.assertFalse(details["current_state_timestamp_observed"])
        self.assertTrue(details["current_state_model_markers_observed"])
        self.assertIsNone(rows[0]["publishedAt"])
        self.assertIn("Seed-Evolving", rows[0]["sourceContext"])

    def test_official_doc_api_recovers_js_shell_without_weakening_evidence(self):
        vendor = self._vendor()
        vendor["current_state_fetch_url"] = "https://example.com/models/canonical?lang=zh#top"
        html = "<html><body>You need to enable JavaScript to run this app.</body></html>"
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            return FakeJsonResponse(
                {
                    "Result": {
                        "Title": "模型列表",
                        "Content": "最新模型：Seed-Evolving\n最近更新时间：2026.07.20 17:28:20",
                    }
                }
            )

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            http_post=fake_post,
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        details = rows[0]["sourceDetails"]
        self.assertEqual("structured_current_state", details["vendor_record_kind"])
        self.assertEqual("official_doc_api", details["current_state_transport"])
        self.assertEqual("2026.07.20", rows[0]["publishedAt"])
        self.assertEqual(1, len(calls))
        self.assertEqual(_VOLCENGINE_DOC_FETCH_API, calls[0][0])
        self.assertEqual("https://example.com/models/canonical", calls[0][1]["json"]["Url"])

    def test_official_doc_api_generic_content_cannot_masquerade_as_state(self):
        vendor = self._vendor()
        html = "<html><body>You need to enable JavaScript to run this app.</body></html>"

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            http_post=lambda url, **kwargs: FakeJsonResponse(
                {"Result": {"Title": "文档中心", "Content": "API参考 产品简介"}}
            ),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("page_fallback", rows[0]["sourceDetails"]["vendor_record_kind"])

    def test_generic_reachable_page_without_model_state_remains_fallback(self):
        vendor = self._vendor()
        html = "<h1>模型列表</h1><p>文档中心</p><p>API参考</p>"

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("page_fallback", rows[0]["sourceDetails"]["vendor_record_kind"])


if __name__ == "__main__":
    unittest.main()