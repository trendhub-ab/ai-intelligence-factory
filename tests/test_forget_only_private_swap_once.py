"""Provider-free regression for the one-off private Forget-Only swap.

No live Notion, GitHub write, Gemini, or note.com access.
"""
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from operations import forget_only_private_swap_once as swap


class OneOffSwapTest(unittest.TestCase):
    def test_exact_private_stage_read_is_sha_bound(self):
        body = "# Sample Title\n\n## どんな内容？\n\n### 元情報\n"
        expected = hashlib.sha256(body.encode()).hexdigest()
        result = {"results": [{
            "object": "page", "id": "test-stage",
            "properties": {"title": {"title": [{"plain_text": swap.STAGE_NAME}]}},
        }]}
        fake = SimpleNamespace(status_code=200, json=lambda: result)
        block = {"type":"code", "code":{"language":"markdown",
                 "rich_text":[{"plain_text":body}]}}
        with patch.object(swap,"ARTICLE_SHA256",expected),\
             patch.object(swap.sync,"_request",return_value=fake),\
             patch.object(swap,"children",return_value=[block]):
            self.assertEqual(swap.stage_article(),(body,"Sample Title"))

    def test_stage_text_mutation_is_rejected_before_mutation(self):
        body = "# Sample Title\n\n## どんな内容？\n\n### 元情報\n"
        response = {"results":[{"object":"page","id":"test-stage",
                      "properties":{"title":{"title":[{"plain_text":swap.STAGE_NAME}]}}}]}
        fake=SimpleNamespace(status_code=200,json=lambda:response)
        block={"type":"code","code":{"language":"markdown",
               "rich_text":[{"plain_text":body+"changed"}]}}
        with patch.object(swap,"ARTICLE_SHA256",hashlib.sha256(body.encode()).hexdigest()),\
             patch.object(swap.sync,"_request",return_value=fake),\
             patch.object(swap,"children",return_value=[block]):
            with self.assertRaisesRegex(swap.SwapBlocked,"user-approved exact text"):
                swap.stage_article()

    def test_owner_destination_id_is_hash_pinned(self):
        queue={"id":"queue","properties":{
           "同期ID":{"rich_text":[{"plain_text":"abcd"*8}]},
           "note下書きID":{"rich_text":[{"plain_text":"nwrongdraft"}]},
           "投稿状態":{"select":{"name":"投稿準備中"}},
           "品質状態":{"select":{"name":"Ready"}},
           "note公開URL":{"url":None},
           "投稿日":{"date":None}
        }}
        with patch.object(swap.sync,"_query_db",return_value=[queue]):
            with self.assertRaisesRegex(swap.SwapBlocked,"Unexpected draft ID"):
                swap.queue_row("abcd"*8)

    def test_only_ready_title_and_cover_are_written(self):
        result=swap.page_properties("New title","https://example.com/image.png")
        props=result["properties"]
        self.assertEqual(set(props),{"note記事タイトル","アイキャッチ","記事状態"})
        self.assertEqual(props["記事状態"]["select"]["name"],"Ready")
        self.assertEqual(props["note記事タイトル"]["rich_text"][0]["text"]["content"],"New title")

    def test_no_provider_code_or_publication_surface(self):
        from pathlib import Path
        script=(Path(__file__).resolve().parents[1]/"operations"/"forget_only_private_swap_once.py").read_text()
        self.assertNotIn("GEMINI_API_KEY",script)
        self.assertNotIn("page.click('公開')",script)
        self.assertNotIn("note.com/notes/new",script)
        self.assertIn("new_draft_created\":False",script)
        self.assertIn("existing.apply_current_article_to_existing_draft",script)


if __name__=="__main__":
    unittest.main()
