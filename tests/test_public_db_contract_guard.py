import unittest

import public_db_contract_guard as guard


class PublicDbContractGuardTests(unittest.TestCase):
    def test_schema_requires_url_and_single_title(self):
        schema = {
            "記事名": {"type": "title"},
            "元情報URL": {"type": "url"},
        }
        self.assertEqual(guard.validate_schema(schema), "記事名")
        with self.assertRaises(ValueError):
            guard.validate_schema({"記事名": {"type": "title"}})

    def test_pages_reject_duplicate_canonical_urls(self):
        pages = [
            {
                "id": "a",
                "properties": {
                    "記事名": {"type": "title", "title": [{"plain_text": "A"}]},
                    "元情報URL": {"type": "url", "url": "https://example.com/x/"},
                },
            },
            {
                "id": "b",
                "properties": {
                    "記事名": {"type": "title", "title": [{"plain_text": "B"}]},
                    "元情報URL": {"type": "url", "url": "https://EXAMPLE.com/x"},
                },
            },
        ]
        with self.assertRaises(ValueError):
            guard.validate_pages(pages, "記事名")

    def test_manual_row_without_url_is_preserved(self):
        pages = [
            {
                "id": "manual",
                "properties": {
                    "記事名": {"type": "title", "title": [{"plain_text": "Manual"}]},
                    "元情報URL": {"type": "url", "url": None},
                },
            },
            {
                "id": "managed",
                "properties": {
                    "記事名": {"type": "title", "title": [{"plain_text": "Managed"}]},
                    "元情報URL": {"type": "url", "url": "https://example.com/a"},
                },
            },
        ]
        result = guard.validate_pages(pages, "記事名")
        self.assertEqual(result["records"], 2)
        self.assertEqual(result["manual_without_url"], 1)
        self.assertEqual(result["duplicate_urls"], 0)
        self.assertTrue(result["zero_gemini_calls"])
        self.assertEqual(result["mcp_sql_calls"], 0)

    def test_managed_row_requires_title(self):
        pages = [
            {
                "id": "bad",
                "properties": {
                    "記事名": {"type": "title", "title": []},
                    "元情報URL": {"type": "url", "url": "https://example.com/a"},
                },
            }
        ]
        with self.assertRaises(ValueError):
            guard.validate_pages(pages, "記事名")


if __name__ == "__main__":
    unittest.main()
