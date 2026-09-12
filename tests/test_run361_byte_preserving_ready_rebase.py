from __future__ import annotations

import unittest
from unittest.mock import patch

import publication_contract as contract
import run361_byte_preserving_ready_rebase as run361


def _block(body: str, policy: str, *, manuscript_sha: str | None = None) -> dict:
    sha = manuscript_sha if manuscript_sha is not None else contract.manuscript_sha256(body)
    caption = (
        f"{contract.READY_CAPTION_PREFIX}contract={contract.CONTRACT_ID}"
        f"|policy_sha256={policy}|manuscript_sha256={sha}"
    )
    return {
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": body}}],
            "caption": [{"type": "text", "text": {"content": caption}}],
            "language": "markdown",
        },
    }


class Run361BytePreservingReadyRebaseTests(unittest.TestCase):
    def test_exact_historical_block_is_eligible(self):
        historical = "a" * 64
        body = "# approved manuscript\n本文は一切変更しない。"
        with patch.object(contract, "is_current_ready_block", return_value=False):
            decision = run361.classify_ready_blocks([_block(body, historical)], historical)
        self.assertEqual(decision.status, "eligible")
        self.assertEqual(decision.body, body)
        self.assertEqual(decision.manuscript_sha256, contract.manuscript_sha256(body))

    def test_body_sha_mismatch_is_never_eligible(self):
        historical = "a" * 64
        body = "body"
        with patch.object(contract, "is_current_ready_block", return_value=False):
            decision = run361.classify_ready_blocks(
                [_block(body, historical, manuscript_sha="b" * 64)], historical
            )
        self.assertEqual(decision.status, "skip")
        self.assertIn("safe_historical_match_count=0", decision.reason)

    def test_older_safe_block_is_refused_when_newer_ready_family_exists(self):
        historical = "a" * 64
        safe = _block("safe old", historical)
        newer = _block("newer unknown", "c" * 64)
        with patch.object(contract, "is_current_ready_block", return_value=False):
            decision = run361.classify_ready_blocks([safe, newer], historical)
        self.assertEqual(decision.status, "skip")
        self.assertEqual(decision.reason, "safe_block_is_not_latest_ready_family")

    def test_existing_current_block_short_circuits_rebase(self):
        historical = "a" * 64
        body = "already current"
        block = _block(body, historical)
        with patch.object(contract, "is_current_ready_block", return_value=True):
            decision = run361.classify_ready_blocks([block], historical)
        self.assertEqual(decision.status, "current")

    def test_current_code_block_round_trips_exact_bytes(self):
        body = "日本語🙂\n" + ("x" * 5000) + "\n末尾"
        with patch.object(contract, "policy_sha256", return_value="d" * 64):
            block = run361._current_code_block(body)
        import note_ready_sync as sync
        self.assertEqual(sync._code_body(block), body)
        self.assertEqual(
            contract.manuscript_sha256(sync._code_body(block)),
            contract.manuscript_sha256(body),
        )

    def test_apply_confirmation_is_hard_coded(self):
        self.assertEqual(run361.APPLY_CONFIRMATION, "REBASE_IDENTICAL_BODY")
        self.assertEqual(run361.DEFAULT_MAX_PAGES, 40)


if __name__ == "__main__":
    unittest.main()
