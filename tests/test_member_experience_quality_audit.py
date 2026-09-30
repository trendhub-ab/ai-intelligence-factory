from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

import member_experience_quality_audit as audit
import member_presentation_body_sync as body
import member_presentation_sync as mps
import run219_member_human_language_ui as run219


def _callout(name: str, label: str):
    return {
        "id": name, "type": "callout",
        "callout": {"rich_text": body._rich_text(label)},
    }


def _headings(*names: str):
    return [body._heading(name) for name in names]


class PaidDBReadOnlyExperienceAuditTests(unittest.TestCase):
    def _states(self):
        return {
            "dify": {
                "page_id": "dify", "sync_id": "dify-record",
                "name": "langgenius/dify", "last_reviewed": "2026-08-29T03:14:00Z",
            },
            "manual": {
                "page_id": "manual", "sync_id": "manually-curated-record",
                "name": "Manual item", "last_reviewed": "",
            },
        }

    def test_production_duplicate_variants_detected_without_writes(self):
        roots = {
            "dify": [
                _callout("generated-old", run219.NEW_VISIBLE_CALLOUT_LABEL),
                _callout("generated-current", run219.NEW_VISIBLE_CALLOUT_LABEL),
                _callout("human", "手書きの補足"),
            ],
            "generated-old": _headings(
                "これは何？", "いま、使える？", "使える場面", "次の一手"
            ),
            "generated-current": _headings(
                "これは何？", "いま、使える？",
                "使う前に確認すること", "試す・導入する次の一手"
            ),
            "manual": [
                _callout("manual-same-label", run219.NEW_VISIBLE_CALLOUT_LABEL)
            ],
            "manual-same-label": _headings("担当者のメモ"),
        }
        accesses = []
        def reader(identifier):
            accesses.append(identifier)
            return roots.get(identifier, [])
        states = self._states()
        with patch.object(mps, "_destination_state", side_effect=lambda p: states[p["id"]]):
            result = audit.inspect(
                [{"id": "dify"}, {"id": "manual"}],
                reader,
                today=date(2026, 9, 30),
            )
        self.assertTrue(result["read_only"])
        self.assertEqual(0, result["gemini_provider_calls"])
        self.assertEqual(1, result["counts"]["duplicates_confirmed"])
        self.assertEqual("dify", result["duplicates_confirmed"][0]["page_id"])
        self.assertEqual(2, result["duplicates_confirmed"][0]["count"])
        self.assertEqual(1, result["counts"]["same_label_unclassified"])
        self.assertEqual("manual", result["same_label_unclassified"][0]["page_id"])
        self.assertEqual(1, result["counts"]["missing_source_review_date"])
        self.assertEqual(1, result["counts"]["source_review_older_than_30_days"])
        self.assertEqual(32, result["source_review_older_than_30_days"][0]["age_days"])
        self.assertIn("generated-old", accesses)
        self.assertIn("manual-same-label", accesses)

    def test_does_not_infer_staleness_from_page_last_edited_time(self):
        with patch.object(mps, "_destination_state", return_value={
            "page_id": "only", "sync_id": "r", "name": "item",
            "last_reviewed": "2026-09-29",
        }):
            result = audit.inspect(
                [{"id": "only", "last_edited_time": "2020-01-01T00:00:00Z"}],
                lambda _id: [],
                today=date(2026, 9, 30),
            )
        self.assertEqual([], result["source_review_older_than_30_days"])
        self.assertEqual(1, result["counts"]["no_visible_generated_body"])

    def test_current_and_historical_generator_bodies_are_both_classified(self):
        cache = {}
        old = _callout("historical", run219.NEW_VISIBLE_CALLOUT_LABEL)
        current = _callout("current", run219.NEW_VISIBLE_CALLOUT_LABEL)
        cache["historical"] = _headings(
            "いま、使える？", "使える場面", "次の一手"
        )
        cache["current"] = _headings(
            "いま、使える？", "使う前に確認すること", "試す・導入する次の一手"
        )
        self.assertTrue(run219._looks_like_generated_member_callout(old, cache))
        self.assertTrue(run219._looks_like_generated_member_callout(current, cache))


if __name__ == "__main__":
    unittest.main()
