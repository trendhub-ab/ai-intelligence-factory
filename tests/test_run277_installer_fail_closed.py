import unittest
from types import SimpleNamespace

import article_revalidation


class Run277InstallerFailClosedTests(unittest.TestCase):
    def test_fileless_minimal_orchestration_double_is_compatibility_noop(self):
        pipeline = SimpleNamespace()
        result = article_revalidation.install_full_recovery(pipeline)
        self.assertIs(result, pipeline)
        self.assertFalse(hasattr(pipeline, article_revalidation._INSTALLED_ATTR))

    def test_real_like_pipeline_missing_canonical_backlog_fails_closed(self):
        pipeline = SimpleNamespace(__file__="/app/pipeline.py")
        with self.assertRaisesRegex(RuntimeError, "process_article_backlog"):
            article_revalidation.install_full_recovery(pipeline)


if __name__ == "__main__":
    unittest.main()
