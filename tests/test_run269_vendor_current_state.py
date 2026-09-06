from __future__ import annotations

import unittest

from run269_vendor_current_state import (
    OFFICIAL_VENDOR_REGISTRY,
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


class Run269VendorCurrentStateTests(unittest.TestCase):
    def _vendor(self):
        return {
            "vendor": "ByteDance Doubao/Seed",
            "region": "CN",
            "release_url": "https://example.com/models",
            "allowed_domains": ("example.com",),
            "current_state_page": True,
            "current_state_label": "公式モデル一覧",
        }

    def test_bytedance_registry_uses_official_model_list_current_state(self):
        row = next(row for row in OFFICIAL_VENDOR_REGISTRY if row["vendor"] == "ByteDance Doubao/Seed")
        self.assertTrue(row["current_state_page"])
        self.assertIn("1799865", row["release_url"])

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
        # Preserve the concrete official evidence instead of replacing it with a
        # synthetic explanation when precision extraction already found the model row.
        self.assertIn("Seed-Evolving", rows[0]["sourceContext"])

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
