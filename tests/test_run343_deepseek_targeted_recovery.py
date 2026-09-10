import types
import unittest
from unittest.mock import patch

import run343_deepseek_targeted_recovery as run343


class Run343DeepSeekTargetedRecoveryTests(unittest.TestCase):
    def _pipeline(self, status="Quality Failed"):
        p = types.SimpleNamespace()
        p.CONTENT_STATUS_QUALITY_FAILED = "Quality Failed"
        p.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW = "Needs Editorial Review"
        return p, {
            "notion_page_id": "page-deepseek",
            "revalidation_article_status": "Needs Editorial Review",
            "revalidation_content_status": status,
            "repo": {"nameWithOwner": run343.TARGET_NAME, "url": run343.TARGET_URL},
        }

    def test_exact_name_and_url_select_one_target(self):
        p, target = self._pipeline()
        noise = dict(target)
        noise["repo"] = dict(target["repo"], url="https://news.ycombinator.com/item?id=wrong")
        with patch.object(run343.article_revalidation, "select_revalidation_items", return_value=[noise, target]):
            self.assertIs(run343.select_exact_target(p), target)

    def test_refuses_name_only_collision(self):
        p, target = self._pipeline()
        collision = dict(target)
        collision["repo"] = dict(target["repo"], url="https://example.com/not-the-target")
        with patch.object(run343.article_revalidation, "select_revalidation_items", return_value=[collision]):
            with self.assertRaisesRegex(RuntimeError, "exact target mismatch"):
                run343.select_exact_target(p)

    def test_refuses_when_target_is_no_longer_quality_failed(self):
        p, target = self._pipeline(status="Deep Dive")
        with patch.object(run343.article_revalidation, "select_revalidation_items", return_value=[target]):
            with self.assertRaisesRegex(RuntimeError, "no longer Quality Failed"):
                run343.select_exact_target(p)

    def test_refuses_duplicate_exact_matches(self):
        p, target = self._pipeline()
        with patch.object(run343.article_revalidation, "select_revalidation_items", return_value=[target, dict(target)]):
            with self.assertRaisesRegex(RuntimeError, "found=2"):
                run343.select_exact_target(p)


if __name__ == "__main__":
    unittest.main()
