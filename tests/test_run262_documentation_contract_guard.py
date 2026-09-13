from __future__ import annotations

import unittest

import run262_documentation_contract_guard as guard


class ProviderRoutingAndFanoutGuardTests(unittest.TestCase):
    def _current(self):
        return {
            "one_shot": guard.ONE_SHOT.read_text(encoding="utf-8"),
            "note_ready": guard.NOTE_READY.read_text(encoding="utf-8"),
            "subscriber": guard.SUBSCRIBER.read_text(encoding="utf-8"),
            "cross_db": guard.CROSS_DB.read_text(encoding="utf-8"),
            "routing": guard.ROUTING.read_text(encoding="utf-8"),
        }

    def test_current_semantic_contract_is_clean(self):
        self.assertEqual(guard.audit_texts(**self._current()), [])

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
        self.assertTrue(any("provider_routing_live_quality_path_missing" in item for item in failures))

    def test_non_gemini_primary_is_rejected(self):
        values = self._current()
        values["routing"] = values["routing"].replace(
            'PRIMARY_MODEL = "gemini-3.8-flash"',
            'PRIMARY_MODEL = "other-provider-model"',
            1,
        )
        failures = guard.audit_texts(**values)
        self.assertIn("provider_routing_primary_not_gemini", failures)

    def test_retired_provider_reintroduction_is_rejected(self):
        values = self._current()
        values["routing"] += "\n# groq provider adapter\n"
        failures = guard.audit_texts(**values)
        self.assertIn("provider_routing_retired_provider_reintroduced:groq", failures)

    def test_documentation_wording_is_not_part_of_executable_contract(self):
        # Deliberately no canonical-spec/reference-doc input: prose edits must not weaken
        # or block the executable routing/fan-out safety contract.
        self.assertNotIn("spec", self._current())
        self.assertNotIn("run261_doc", self._current())


if __name__ == "__main__":
    unittest.main()
