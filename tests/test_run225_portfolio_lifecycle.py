import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import run225_portfolio_lifecycle as overlay


NOW = datetime(2026, 9, 4, 7, 0, tzinfo=timezone.utc)


def record(name: str, source: str, days: int):
    return SimpleNamespace(
        name=name,
        source=(source,),
        published_at=(NOW - timedelta(days=days)).isoformat(),
        analyzed_at=None,
        last_reviewed=None,
        source_summary="",
    )


class PortfolioLifecycleOverlayTests(unittest.TestCase):
    def test_archive_is_removed_before_authoritative_planner(self):
        seen = []

        def original(records, limit=30, max_source_share=0.60, now=None):
            rows = list(records)
            seen.extend(rows)
            return rows[:limit]

        module = SimpleNamespace(plan_candidates=original)
        overlay.install_on(module)
        fresh = record("fresh", "HackerNews", 5)
        old_news = record("old acquisition", "HackerNews", 120)
        old_repo = record("project/repo", "GitHub", 120)
        result = module.plan_candidates([old_news, fresh, old_repo], now=NOW)

        self.assertEqual(["fresh", "project/repo"], [x.name for x in result])
        self.assertEqual(["fresh", "project/repo"], [x.name for x in seen])

    def test_aging_remains_reviewable(self):
        module = SimpleNamespace(plan_candidates=lambda records, **kwargs: list(records))
        overlay.install_on(module)
        result = module.plan_candidates([record("aging", "ProductHunt", 45)], now=NOW)
        self.assertEqual(["aging"], [x.name for x in result])

    def test_overlay_does_not_mutate_records(self):
        module = SimpleNamespace(plan_candidates=lambda records, **kwargs: list(records))
        overlay.install_on(module)
        item = record("old repo", "GitHub", 150)
        before = dict(vars(item))
        module.plan_candidates([item], now=NOW)
        self.assertEqual(before, vars(item))


if __name__ == "__main__":
    unittest.main()
