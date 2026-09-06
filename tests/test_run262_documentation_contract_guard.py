from __future__ import annotations

import unittest

import run262_documentation_contract_guard as guard


class Run262DocumentationContractGuardTests(unittest.TestCase):
    def _current(self):
        return {
            "spec": guard.SPEC.read_text(encoding="utf-8"),
            "one_shot": guard.ONE_SHOT.read_text(encoding="utf-8"),
            "note_ready": guard.NOTE_READY.read_text(encoding="utf-8"),
            "subscriber": guard.SUBSCRIBER.read_text(encoding="utf-8"),
            "cross_db": guard.CROSS_DB.read_text(encoding="utf-8"),
            "routing": guard.ROUTING.read_text(encoding="utf-8"),
            "run261_doc": guard.RUN261_DOC.read_text(encoding="utf-8"),
            "quota_doc": guard.QUOTA_DOC.read_text(encoding="utf-8"),
        }

    def test_current_run261_documentation_contract_is_clean(self):
        self.assertEqual(guard.audit_texts(**self._current()), [])

    def test_old_passive_one_shot_spec_is_rejected(self):
        values = self._current()
        values["spec"] += (
            "\nSubscriber Decision Brief Sync` の実在するworkflow_run上流は "
            "**`Daily Intelligence & Content Pipeline [ONE-SHOT]`**\n"
        )
        failures = guard.audit_texts(**values)
        self.assertTrue(any("canonical_spec_retains_obsolete_contract" in item for item in failures))

    def test_missing_run261_model_baseline_is_rejected(self):
        values = self._current()
        values["spec"] = values["spec"].replace(
            "Article Model Routing Baseline: **Run261",
            "Article Model Routing Baseline: **Run260",
            1,
        )
        failures = guard.audit_texts(**values)
        self.assertTrue(any("canonical_spec_missing_run261_contract" in item for item in failures))

    def test_passive_duplicate_trigger_is_rejected(self):
        values = self._current()
        values["note_ready"] = values["note_ready"].replace(
            "  workflow_dispatch:\n",
            "  workflow_dispatch:\n  workflow_run:\n    workflows:\n      - Daily Intelligence & Content Pipeline [ONE-SHOT]\n    types: [completed]\n",
            1,
        )
        failures = guard.audit_texts(**values)
        self.assertIn("one_shot_passive_duplicate_trigger:note-ready-sync.yml", failures)

    def test_missing_explicit_gh_pat_fanout_is_rejected(self):
        values = self._current()
        values["one_shot"] = values["one_shot"].replace(
            "GH_TOKEN: ${{ secrets.GH_PAT }}",
            "GH_TOKEN: ${{ github.token }}",
            1,
        )
        failures = guard.audit_texts(**values)
        self.assertTrue(any("one_shot_explicit_fanout_missing" in item for item in failures))

    def test_quality_live_entrypoint_removal_is_rejected(self):
        values = self._current()
        values["routing"] = values["routing"].replace(
            "pipeline_module._call_deep_dive_pool = call_deep_dive_pool_run261",
            "# removed live routing assignment",
            1,
        )
        failures = guard.audit_texts(**values)
        self.assertTrue(any("run261_live_routing_missing" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
