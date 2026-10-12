import unittest
from unittest.mock import patch

import note_ready_sync as sync
import publication_contract as contract


def code_block(body: str, caption: str) -> dict:
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": [{"plain_text": caption, "text": {"content": caption}}],
        },
    }


class SingleCanonicalReadyContractTests(unittest.TestCase):
    def test_delivery_fails_closed_when_two_current_ready_manuscripts_exist(self):
        old = "# Old title\n\n" + ("old body " * 80)
        current = "# Current title\n\n" + ("current body " * 80)
        blocks = [
            code_block(old, contract.current_ready_caption(old)),
            code_block(current, contract.current_ready_caption(current)),
        ]

        with patch.object(sync, "_block_children", return_value=blocks):
            self.assertEqual("", sync._source_current_ready_manuscript("page"))
            self.assertFalse(sync._source_has_current_ready_manuscript("page"))

    def test_delivery_accepts_exactly_one_current_ready_manuscript(self):
        current = "# Current title\n\n" + ("current body " * 80)
        blocks = [code_block(current, contract.current_ready_caption(current))]

        with patch.object(sync, "_block_children", return_value=blocks):
            self.assertEqual(current, sync._source_current_ready_manuscript("page"))
            self.assertTrue(sync._source_has_current_ready_manuscript("page"))


if __name__ == "__main__":
    unittest.main()
