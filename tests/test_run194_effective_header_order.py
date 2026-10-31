"""Regression: real production entrypoint must keep the official Run193 header flow.

Run #41149545373 reached the *old* base._upload_header_image and failed with
"note header-image control was not found". run194_note_current_contract.install()
overrode Run193's newer UI after cloud.install(). Test the effective function in
a clean interpreter, never just source inspection. No browser, credentials or API.
"""
from __future__ import annotations

import subprocess
import sys
import unittest


SCRIPT = r"""
from unittest.mock import patch
import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run193_note_official_header_upload as official
import run194_note_current_contract as legacy
import run194_note_persistent_cloud as entry
import note_delivery_runtime as delivery

# Reproduce the ordering defect deterministically before using the fixed entrypoint.
cloud.install()
assert base._upload_header_image is official._upload_header_image
legacy.install()
assert base._upload_header_image is legacy._upload_header_image, "regression fixture no longer reproduces"
assert base._upload_header_image is not official._upload_header_image

# Do not call note or any provider: only exercise the full installed overlay stack.
with patch.object(entry.current_contract, "run_base_main_with_safe_noop", return_value=None):
    entry.main()

assert base._upload_header_image is official._upload_header_image, "official header image path must win"
assert base._upload_header_image is not legacy._upload_header_image
assert base._create_browser_draft is cloud._create_browser_draft, "persistent Chrome lifecycle changed"
assert base._paste_manuscript is legacy._trusted_clipboard_paste, "current contract paste weakened"
assert getattr(base, "_p0b_durable_delivery_installed", False), "ledger authority missing"
assert getattr(base, "_run417_body_verification_installed", False), "body verification missing"
assert getattr(base, "_run222_note_installed", False), "presentation guard missing"
assert callable(base._save_draft_and_verify), "shared persistence proof missing"
print("PRODUCTION_EFFECTIVE_HEADER=RUN193; LEGACY_PASTE_GUARD=OK; DURABLE_LEDGER=OK")
"""


class Run194EffectiveHeaderOrderTests(unittest.TestCase):
    def test_effective_production_entrypoint_keeps_official_header_upload(self):
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT], check=False, capture_output=True,
            text=True, timeout=25,
        )
        self.assertEqual(
            result.returncode, 0,
            msg=f"stdout={result.stdout[-1200:]} stderr={result.stderr[-2400:]}",
        )
        self.assertIn("PRODUCTION_EFFECTIVE_HEADER=RUN193", result.stdout)

    def test_no_live_note_or_publishing_is_attempted(self):
        self.assertNotIn("page.goto(", SCRIPT)
        self.assertNotIn("create_issue", SCRIPT)
        self.assertNotIn("workflow_dispatch", SCRIPT)
        self.assertNotIn("note.com/new", SCRIPT)


if __name__ == "__main__":
    unittest.main()
