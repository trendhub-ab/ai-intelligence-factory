import unittest
from unittest.mock import MagicMock, patch

import pipeline
import publication_contract as contract


def response(status_code=200, json_data=None, text=""):
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_data or {}
    res.text = text
    return res


def manuscript_block(block_id: str, body: str, caption: str) -> dict:
    return {
        "id": block_id,
        "type": "code",
        "code": {
            "language": "markdown",
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": ([{"plain_text": caption, "text": {"content": caption}}] if caption else []),
        },
    }


def is_review_properties_patch(payload) -> bool:
    props = (payload or {}).get("properties") or {}
    article = props.get(pipeline.PROP_ARTICLE_STATUS) or {}
    return ((article.get("select") or {}).get("name") == pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW)


class ReviewSingleCanonicalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.key.start()
        self.addCleanup(self.key.stop)

    def _persist(self, body="canonical review"):
        return pipeline.persist_notion_needs_editorial_review(
            "page-1", "repo", body, {}, ["editorial reason"]
        )

    def test_cleanup_failure_blocks_review_status_commit(self):
        body = "canonical review"
        canonical = manuscript_block("canonical", body, pipeline.MANUSCRIPT_CAPTION_REVIEW)
        stale_ready = manuscript_block("old-ready", "old ready", contract.current_ready_caption("old ready"))
        review_commits = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/pages/" in url and is_review_properties_patch(json):
                review_commits.append(url)
            return response(200)

        with patch.object(pipeline.requests, "get", return_value=response(200, {"results": [canonical, stale_ready]})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=response(500, text="archive failed")):
            result = self._persist(body)

        self.assertFalse(result)
        self.assertEqual(review_commits, [])

    def test_stale_ready_review_and_captionless_are_archived_before_review_commit(self):
        body = "canonical review"
        canonical = manuscript_block("canonical", body, pipeline.MANUSCRIPT_CAPTION_REVIEW)
        stale_ready = manuscript_block("old-ready", "old ready", contract.current_ready_caption("old ready"))
        stale_review = manuscript_block("old-review", "old review", pipeline.MANUSCRIPT_CAPTION_REVIEW)
        captionless = manuscript_block("legacy", "legacy body", "")
        state = {"cleaned": False}
        events = []

        def fake_get(url, headers=None, timeout=None):
            blocks = [canonical] if state["cleaned"] else [canonical, stale_ready, stale_review, captionless]
            return response(200, {"results": blocks})

        def fake_delete(url, headers=None, timeout=None):
            events.append(("delete", url))
            if len([x for x in events if x[0] == "delete"]) >= 3:
                state["cleaned"] = True
            return response(200)

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/pages/" in url and is_review_properties_patch(json):
                events.append(("review-properties", url))
            return response(200)

        with patch.object(pipeline.requests, "get", side_effect=fake_get), \
             patch.object(pipeline.requests, "delete", side_effect=fake_delete), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._persist(body)

        self.assertTrue(result)
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds.count("delete"), 3)
        self.assertIn("review-properties", kinds)
        self.assertLess(max(i for i, kind in enumerate(kinds) if kind == "delete"), kinds.index("review-properties"))

    def test_regeneration_appends_new_review_then_removes_old_before_commit(self):
        old = manuscript_block("old-review", "old review", pipeline.MANUSCRIPT_CAPTION_REVIEW)
        new_body = "new canonical review"
        state = {"blocks": [old]}
        events = []

        def fake_get(url, headers=None, timeout=None):
            return response(200, {"results": list(state["blocks"])})

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url and url.endswith("/children"):
                events.append(("append", url))
                state["blocks"].append(
                    manuscript_block("new-review", new_body, pipeline.MANUSCRIPT_CAPTION_REVIEW)
                )
                return response(200, {"results": [{"id": "new-review"}]})
            if "/pages/" in url and is_review_properties_patch(json):
                events.append(("review-properties", url))
            return response(200)

        def fake_delete(url, headers=None, timeout=None):
            events.append(("delete", url))
            state["blocks"] = [b for b in state["blocks"] if b["id"] != "old-review"]
            return response(200)

        with patch.object(pipeline.requests, "get", side_effect=fake_get), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", side_effect=fake_delete):
            result = self._persist(new_body)

        self.assertTrue(result)
        self.assertEqual([b["id"] for b in state["blocks"]], ["new-review"])
        kinds = [kind for kind, _ in events]
        self.assertLess(kinds.index("append"), kinds.index("delete"))
        self.assertLess(kinds.index("delete"), kinds.index("review-properties"))


if __name__ == "__main__":
    unittest.main()
