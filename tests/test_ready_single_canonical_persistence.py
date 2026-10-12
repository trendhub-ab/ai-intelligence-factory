import unittest
from unittest.mock import MagicMock, patch

import pipeline


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


def is_ready_properties_patch(payload) -> bool:
    props = (payload or {}).get("properties") or {}
    article = props.get(pipeline.PROP_ARTICLE_STATUS) or {}
    return ((article.get("select") or {}).get("name") == pipeline.ARTICLE_STATUS_READY)


class ReadySingleCanonicalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.key.start()
        self.addCleanup(self.key.stop)

    def _upgrade(self, body="canonical manuscript"):
        return pipeline.upgrade_notion_page_with_report(
            "page-1", "repo", "https://example.com/source",
            80, "breakdown", "what", "why", "why-not", "action",
            "MIT", body,
        )

    def test_stale_existing_ready_body_cannot_commit_ready_properties(self):
        stale = manuscript_block("stale-ready", "old manuscript", pipeline.MANUSCRIPT_CAPTION_READY)
        ready_commits = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/pages/" in url and is_ready_properties_patch(json):
                ready_commits.append(url)
            return response(200, {"results": []})

        with patch.object(pipeline.requests, "get", return_value=response(200, {"results": [stale]})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._upgrade("new canonical manuscript")

        self.assertFalse(result)
        self.assertEqual(ready_commits, [], "Ready properties must not commit without the expected canonical body")

    def test_stale_review_cleanup_failure_blocks_ready_commit(self):
        body = "canonical manuscript"
        canonical = manuscript_block("canonical", body, pipeline.MANUSCRIPT_CAPTION_READY)
        review = manuscript_block("old-review", "old review manuscript", pipeline.MANUSCRIPT_CAPTION_REVIEW)
        ready_commits = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/pages/" in url and is_ready_properties_patch(json):
                ready_commits.append(url)
            return response(200)

        with patch.object(pipeline.requests, "get", return_value=response(200, {"results": [canonical, review]})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=response(500, text="archive failed")):
            result = self._upgrade(body)

        self.assertFalse(result)
        self.assertEqual(ready_commits, [], "Ready properties must wait for stale manuscript cleanup")

    def test_stale_manuscripts_are_archived_before_ready_property_commit(self):
        body = "canonical manuscript"
        canonical = manuscript_block("canonical", body, pipeline.MANUSCRIPT_CAPTION_READY)
        old_ready = manuscript_block("old-ready", "old ready manuscript", pipeline.MANUSCRIPT_CAPTION_READY)
        review = manuscript_block("old-review", "old review manuscript", pipeline.MANUSCRIPT_CAPTION_REVIEW)
        state = {"cleaned": False}
        events = []

        def fake_get(url, headers=None, timeout=None):
            blocks = [canonical] if state["cleaned"] else [canonical, old_ready, review]
            return response(200, {"results": blocks})

        def fake_delete(url, headers=None, timeout=None):
            events.append(("delete", url))
            if len([event for event in events if event[0] == "delete"]) >= 2:
                state["cleaned"] = True
            return response(200)

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/pages/" in url and is_ready_properties_patch(json):
                events.append(("ready-properties", url))
            elif "/blocks/" in url:
                events.append(("children", url))
            return response(200)

        with patch.object(pipeline.requests, "get", side_effect=fake_get), \
             patch.object(pipeline.requests, "delete", side_effect=fake_delete), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._upgrade(body)

        self.assertTrue(result)
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds.count("delete"), 2)
        self.assertIn("ready-properties", kinds)
        self.assertLess(max(i for i, kind in enumerate(kinds) if kind == "delete"), kinds.index("ready-properties"))


if __name__ == "__main__":
    unittest.main()
