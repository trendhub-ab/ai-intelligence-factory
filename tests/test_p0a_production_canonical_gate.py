from __future__ import annotations

import unittest

import note_document_contract as contract
import note_draft_automation as draft
import run190_note_persistent_cloud as cloud


class FakeBody:
    def __init__(self, actual_text: str, *, tag: str = "p") -> None:
        self.actual_text = actual_text
        self.tag = tag

    def inner_text(self, timeout=5000):
        return self.actual_text

    def evaluate(self, script):
        return {
            "type": "root",
            "children": [
                {
                    "type": "element",
                    "tag": self.tag,
                    "attrs": {},
                    "children": [{"type": "text", "text": self.actual_text}],
                }
            ],
        }


class ProductionCanonicalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        cloud.install()

    def test_effective_cloud_renderer_preserves_ordered_list_start(self) -> None:
        source = "3. Alpha\n4. Beta"
        expected = contract.parse_presentation_markdown(source)
        actual = contract.parse_safe_html(draft._markdown_to_safe_html(source))
        receipt = contract.compare_documents(expected, actual)
        self.assertTrue(receipt["canonical_match"], receipt)

    def test_effective_cloud_verifier_rejects_semantic_text_mutation_outside_old_anchors(self) -> None:
        expected = ("A" * 100) + "10秒" + ("B" * 100) + ("C" * 100)
        actual = ("A" * 100) + "99秒" + ("B" * 100) + ("C" * 100)

        with self.assertRaises(draft.NoteDraftError) as caught:
            draft._verify_body_content(FakeBody(actual), expected)

        self.assertNotIn("99秒", str(caught.exception))
        self.assertNotIn(expected, str(caught.exception))

    def test_effective_cloud_verifier_fails_closed_on_unknown_dom_wrapper(self) -> None:
        expected = "本文" * 120

        with self.assertRaises(draft.NoteDraftError):
            draft._verify_body_content(FakeBody(expected, tag="section"), expected)


if __name__ == "__main__":
    unittest.main()
