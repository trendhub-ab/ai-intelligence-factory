"""Regression guard for retired GenRec one-shot recovery workflows.

These workflow entry points were article-specific recovery/diagnostic assets for the
Netflix GenRec repair chain completed by Runs 297-302.  Production helpers and the
normal Note Ready/publication workflows remain in place; only the historical
push-triggered one-shot entry points are retired.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RETIRED_WORKFLOWS = (
    ".github/workflows/run297-298-genrec-inplace-refresh.yml",
    ".github/workflows/run298-existing-draft-route-retry.yml",
    ".github/workflows/run298-existing-header-retry.yml",
    ".github/workflows/run298-header-readonly-diagnostics.yml",
    ".github/workflows/run299-genrec-body-structure-diagnostic.yml",
    ".github/workflows/run300-genrec-final-body-repair.yml",
    ".github/workflows/run301-genrec-summary-restore.yml",
    ".github/workflows/run302-genrec-publication-reconcile.yml",
)


def test_completed_run297_302_one_shot_workflow_entry_points_are_retired():
    stale = [path for path in RETIRED_WORKFLOWS if (ROOT / path).exists()]
    assert stale == [], f"completed one-shot workflows must stay retired: {stale}"
