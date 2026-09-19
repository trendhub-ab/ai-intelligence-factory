from __future__ import annotations

import inspect
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import run_sgps_existing_draft_repair as repair


ROOT = Path(__file__).resolve().parents[1]


class SGPSExistingDraftRepairContractTests(unittest.TestCase):
    def test_exact_target_is_hard_bound(self):
        self.assertEqual("3e0479ffdca981a1b4b6d827f2656d49", repair.SYNC_ID)
        self.assertEqual("3e0479ff-dca9-81ec-9b8a-e79ca7fd2ebb", repair.DESTINATION_PAGE_ID)
        self.assertEqual("REPAIR_SGPS_EXISTING_DRAFT", repair.CONFIRM_TOKEN)

    def test_repaired_title_separates_training_and_hardware_stages(self):
        self.assertEqual(
            "GPU 1台でロボット方策を学習。実機へゼロショット転送する「SGPS」は何を変えるのか？",
            repair.NEW_TITLE,
        )
        first, second = repair.NEW_TITLE.split("。", 1)
        self.assertIn("GPU 1台", first)
        self.assertIn("学習", first)
        self.assertNotIn("実機", first)
        self.assertIn("実機", second)

    def test_manuscript_removes_historical_source_fidelity_failures(self):
        body = repair.load_manuscript()
        self.assertNotIn("RTX 4080", body)
        self.assertNotIn("最適な動きへと収束", body)
        self.assertNotIn("レンダリングを行う必要がなく", body)
        self.assertNotIn("そのままデプロイ", body)
        self.assertNotIn("10Hzの処理サイクル", body)
        self.assertIn("計算グラフから外す", body)
        self.assertIn("蒸留", body)
        self.assertIn("制御ループは50Hz", body)
        self.assertIn("深度エンコーダが10Hz", body)
        self.assertIn("微分可能なダイナミクス", body)

    def test_current_production_gates_accept_repaired_manuscript(self):
        # Runtime-layer installation intentionally mutates the pipeline module. Execute this
        # proof in an isolated interpreter so it cannot change unrelated full-suite tests.
        code = (
            "import json; import run_sgps_existing_draft_repair as r; "
            "print(json.dumps(r.validate_repaired_manuscript(), ensure_ascii=False))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + "\n" + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(result["fact_ok"], result)
        self.assertTrue(result["editorial_ok"], result)
        self.assertEqual("PASS", result["publication_state"], result)
        self.assertEqual("ACCEPTABLE", result["human_state"], result)

    def test_same_edit_route_ignores_query_but_never_changes_note_id(self):
        a = "https://note.com/notes/abc123/edit"
        b = "https://note.com/notes/abc123/edit?foo=bar"
        c = "https://note.com/notes/other/edit"
        self.assertTrue(repair._same_edit_route(a, b))
        self.assertFalse(repair._same_edit_route(a, c))
        self.assertFalse(repair._same_edit_route(a, "https://note.com/new"))

    def test_prepare_only_never_reaches_browser_mutation(self):
        with mock.patch.object(repair, "validate_repaired_manuscript", return_value={
            "fact_ok": True,
            "editorial_ok": True,
            "publication_state": "PASS",
            "human_state": "ACCEPTABLE",
        }), mock.patch.object(repair, "_destination_preflight", return_value={
            "posting_state": "投稿準備中",
            "quality_state": "Ready取消",
        }), mock.patch.object(repair, "_browser_repair") as browser:
            result = repair.run(confirm=repair.CONFIRM_TOKEN, prepare_only=True)
        browser.assert_not_called()
        self.assertEqual("repair_ready", result["status"])
        self.assertFalse(result["new_draft_created"])
        self.assertFalse(result["public_release"])
        self.assertTrue(result["zero_gemini_calls"])

    def test_module_has_no_new_draft_or_public_release_action(self):
        source = inspect.getsource(repair)
        for forbidden in (
            "NOTE_NEW_URL",
            "_create_browser_draft(",
            "_mark_draft_created(",
            "publish_note(",
            "公開に進む",
            "投稿する",
            "_generate_via_chat(",
            "GEMINI_API_KEY",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("_recent_private_edit_urls", source)
        self.assertIn("_same_edit_route(existing_url, saved_url)", source)

    def test_repair_artifact_contains_sources_before_cta(self):
        body = repair.load_manuscript()
        self.assertLess(body.index("### Sources / Evidence"), body.index("### 有料サブスクのご案内"))


if __name__ == "__main__":
    unittest.main()
