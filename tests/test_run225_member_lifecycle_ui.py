import unittest

import run225_member_lifecycle_ui as run225
import run225_stock_lifecycle as lifecycle


class MemberLifecycleRankingTests(unittest.TestCase):
    def _state(self, name, score, state):
        return {
            "name": name,
            "score": score,
            "category": "開発ツール",
            "status": "TEST",
            "confidence": "高",
            "readiness": "高",
            "classification": "実務判断",
            "current_month_change": False,
            "delta": None,
            "rank": None,
            "stock_lifecycle": state,
        }

    def test_archive_never_receives_homepage_rank(self):
        states = [
            self._state("archive-high", 100, lifecycle.ARCHIVE),
            self._state("fresh", 80, lifecycle.FRESH),
        ]
        selected = run225.assign_home_ranks_with_lifecycle(states, limit=3)
        self.assertEqual(["fresh"], [x["name"] for x in selected])
        self.assertIsNone(states[0]["rank"])

    def test_fresh_and_evergreen_rank_before_aging_even_with_lower_score(self):
        states = [
            self._state("aging-high", 99, lifecycle.AGING),
            self._state("fresh", 80, lifecycle.FRESH),
            self._state("evergreen", 79, lifecycle.EVERGREEN),
        ]
        selected = run225.assign_home_ranks_with_lifecycle(states, limit=3)
        self.assertEqual(["fresh", "evergreen", "aging-high"], [x["name"] for x in selected])
        self.assertEqual([1, 2, 3], [x["rank"] for x in selected])

    def test_aging_fills_when_current_pool_is_small(self):
        states = [
            self._state("fresh", 90, lifecycle.FRESH),
            self._state("aging", 85, lifecycle.AGING),
        ]
        selected = run225.assign_home_ranks_with_lifecycle(states, limit=3)
        self.assertEqual(["fresh", "aging"], [x["name"] for x in selected])

    def test_legacy_state_without_lifecycle_remains_backward_compatible(self):
        state = self._state("legacy", 90, lifecycle.FRESH)
        state.pop("stock_lifecycle")
        selected = run225.assign_home_ranks_with_lifecycle([state], limit=3)
        self.assertEqual(["legacy"], [x["name"] for x in selected])


if __name__ == "__main__":
    unittest.main()
