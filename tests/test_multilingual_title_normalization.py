import unittest
from unittest.mock import patch, Mock
import pipeline


class MultilingualTitleNormalizationTests(unittest.TestCase):
    def test_chinese_product_title_gets_japanese_descriptor_without_changing_original(self):
        repo = pipeline.normalize_item(
            source="ProductHunt",
            name="电商出图吧",
            url="https://example.com/product",
            description="AI product image generator for e-commerce listings",
            engagement=10,
        )
        self.assertEqual(repo["nameWithOwner"], "电商出图吧")
        self.assertEqual(repo["originalTitle"], "电商出图吧")
        self.assertEqual(repo["sourceLanguage"], "zh-CN")
        self.assertEqual(repo["displayName"], "EC商品画像生成ツール「电商出图吧」")

    def test_english_and_japanese_titles_remain_unchanged(self):
        en = pipeline.normalize_item("ProductHunt", "GoRules", "https://x", "rules engine", 0)
        ja = pipeline.normalize_item("HackerNews", "日本語タイトル", "https://x", "説明", 0)
        self.assertEqual(en["displayName"], "GoRules")
        self.assertEqual(ja["displayName"], "日本語タイトル")

    def test_unicode_title_match_does_not_collapse_non_latin_to_empty(self):
        self.assertEqual(pipeline._normalize_title_for_match("电商出图吧"), "电商出图吧")
        self.assertNotEqual(pipeline._normalize_title_for_match("电商出图吧"), "")

    def test_source_summary_preserves_original_title_and_language(self):
        repo = pipeline.normalize_item(
            "ProductHunt", "电商出图吧", "https://x", "AI image generator", 0
        )
        summary = pipeline._source_summary_with_original(repo, "AI image generator")
        self.assertIn("Original Title: 电商出图吧", summary)
        self.assertIn("Language: zh-CN", summary)

    def test_stock_notion_name_uses_display_name_not_identity_name(self):
        repo = pipeline.normalize_item(
            "ProductHunt", "电商出图吧", "https://x", "AI product image generator for e-commerce", 0
        )
        fake = Mock(status_code=200)
        fake.json.return_value = {"id": "page-1"}
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "ds"), \
             patch.object(pipeline.requests, "post", return_value=fake) as post:
            page_id = pipeline.save_screening_metadata_to_notion(repo, 60, "reason")
        self.assertEqual(page_id, "page-1")
        props = post.call_args.kwargs["json"]["properties"]
        title = props[pipeline.PROP_NAME]["title"][0]["text"]["content"]
        self.assertEqual(title, "EC商品画像生成ツール「电商出图吧」")
        summary = props[pipeline.PROP_SOURCE_SUMMARY]["rich_text"][0]["text"]["content"]
        self.assertIn("Original Title: 电商出图吧", summary)

    def test_existing_multilingual_row_is_repaired_without_gemini(self):
        pipeline.EXISTING_NOTION_PAGE_INDEX = [{
            "page_id": "p1", "name": "电商出图吧", "source": "ProductHunt",
            "summary": "AI product image generator for e-commerce listings", "url": "https://x",
        }]
        fake = Mock(status_code=200)
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline.requests, "patch", return_value=fake) as req:
            count = pipeline.repair_existing_multilingual_notion_titles()
        self.assertEqual(count, 1)
        props = req.call_args.kwargs["json"]["properties"]
        title = props[pipeline.PROP_NAME]["title"][0]["text"]["content"]
        self.assertEqual(title, "EC商品画像生成ツール「电商出图吧」")


if __name__ == "__main__":
    unittest.main()
