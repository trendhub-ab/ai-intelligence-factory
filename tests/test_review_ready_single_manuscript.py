from pathlib import Path
import unittest

SOURCE = Path("pipeline.py").read_text(encoding="utf-8")
START = SOURCE.index("def upgrade_notion_page_with_report")
END = SOURCE.find("\ndef ", START + 10)
BODY = SOURCE[START: END if END != -1 else len(SOURCE)]


class ReviewReadySingleManuscriptContractTests(unittest.TestCase):
    def test_review_cleanup_is_required_before_ready_property_commit(self):
        call = "_delete_notion_review_manuscripts_before_ready(page_id, repo_name, headers)"
        self.assertIn(call, BODY)
        self.assertLess(BODY.index(call), BODY.index("# Phase 2:"))
        self.assertIn("Notion Review manuscript cleanup failed before Ready commit", BODY)

    def test_post_commit_best_effort_cleanup_is_removed(self):
        self.assertNotIn("Ready commit後の旧Review原稿整理はbest-effort", BODY)
        self.assertNotIn("[NOTION REVIEW CLEANUP SKIPPED]", BODY)

    def test_properties_http_failure_keeps_formal_manuscript_for_retry(self):
        start = BODY.index("[NOTION UPGRADE PROPERTIES ERROR]")
        end = BODY.index("[NOTION READY COMMITTED]", start)
        failure_block = BODY[start:end]
        self.assertNotIn("_rollback_notion_manuscript_children", failure_block)
        self.assertIn("_mark_pending_retry_or_escalate", failure_block)

    def test_properties_exception_keeps_formal_manuscript_for_retry(self):
        start = BODY.index("[NOTION READY COMMITTED]")
        exc = BODY.index("except Exception as e:", start)
        exception_block = BODY[exc:]
        self.assertNotIn("_rollback_notion_manuscript_children", exception_block)
        self.assertIn("_mark_pending_retry_or_escalate", exception_block)

    def test_existing_formal_manuscript_guard_still_prevents_reappend(self):
        guard = "has_existing_manuscript = _notion_page_has_manuscript_child(page_id, headers)"
        skip = "[NOTION UPGRADE CHILDREN SKIPPED]"
        append = "build_notion_manuscript_children(clean_manuscript)"
        self.assertIn(guard, BODY)
        self.assertIn(skip, BODY)
        self.assertIn(append, BODY)
        self.assertLess(BODY.index(guard), BODY.index(append))


if __name__ == "__main__":
    unittest.main()
