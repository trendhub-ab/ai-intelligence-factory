from __future__ import annotations

from datetime import date
import unittest

import member_reader_quality_policy as policy


class MemberReaderQualityPolicyTests(unittest.TestCase):
    TODAY = date(2026, 10, 1)

    def test_recorded_dates_are_shared_and_not_page_update_dates(self):
        for raw in ("2026-09-30", "2026-09-30T03:00:00Z"):
            self.assertEqual("recorded", policy.review_state(raw, as_of=self.TODAY))
            self.assertEqual("2026年9月30日", policy.review_badge(raw, as_of=self.TODAY))
            self.assertIn("2026年9月30日に確認", policy.review_disclosure(raw, as_of=self.TODAY))
        self.assertNotIn("2026年10月1日に確認",
                         policy.review_disclosure("2026-09-30", as_of=self.TODAY))

    def test_thirty_day_cutoff_and_future_dates_are_honest(self):
        self.assertEqual("recorded", policy.review_state("2026-09-01", as_of=self.TODAY))
        self.assertEqual("older", policy.review_state("2026-08-31", as_of=self.TODAY))
        self.assertIn("30日超", policy.review_badge("2026-08-31", as_of=self.TODAY))
        self.assertIn("30日を超えています",
                      policy.review_disclosure("2026-08-31", as_of=self.TODAY))
        self.assertEqual("future", policy.review_state("2026-10-02", as_of=self.TODAY))
        self.assertEqual("確認日を要確認",
                         policy.review_badge("2026-10-02", as_of=self.TODAY))
        self.assertNotIn("2026年10月2日に確認",
                         policy.review_disclosure("2026-10-02", as_of=self.TODAY))

    def test_missing_and_invalid_date_never_claim_verified_evidence(self):
        self.assertEqual("missing", policy.review_state(None, as_of=self.TODAY))
        self.assertEqual("未記録", policy.review_badge("", as_of=self.TODAY))
        self.assertIn("最終確認日が記録されていません",
                      policy.review_disclosure(None, as_of=self.TODAY))
        for bad in ("2026-99-33", "2026-10-01fake", "not-a-date"):
            self.assertEqual("invalid", policy.review_state(bad, as_of=self.TODAY))
            self.assertIn("不整合", policy.review_disclosure(bad, as_of=self.TODAY))
            self.assertEqual("", policy.display_date(bad))

    def test_status_and_source_links_cannot_claim_unverified_origin(self):
        self.assertIn("使う候補", policy.LONG_STATUS["ADOPT"])
        self.assertIn("検証", policy.status_short("TEST"))
        self.assertNotEqual("ADOPT", policy.status_short("ADOPT"))
        self.assertEqual("参照先 1：comet.com",
                         policy.source_link_label("https://www.comet.com/docs/x"))
        self.assertEqual("参照先 1",
                         policy.source_link_label("http://example.com/unverified"))


if __name__ == "__main__":
    unittest.main()
