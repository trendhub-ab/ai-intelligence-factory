from __future__ import annotations

import unittest

import note_document_contract as contract
import note_draft_automation as draft
import run417_note_body_verification as run417


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def el(tag: str, children=(), **attrs) -> dict:
    return {"type": "element", "tag": tag, "attrs": attrs, "children": list(children)}


def root(*children) -> dict:
    return {"type": "root", "children": list(children)}


class FakeBody:
    def __init__(self, actual_text: str = "", *, tag: str = "p", snapshot: dict | None = None) -> None:
        self.actual_text = actual_text
        self.tag = tag
        self.snapshot = snapshot

    def inner_text(self, timeout=5000):
        return self.actual_text

    def evaluate(self, script):
        if self.snapshot is not None:
            return self.snapshot
        return root(el(self.tag, [text(self.actual_text)]))


class ProductionCanonicalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._missing = object()
        self._old_renderer = draft._markdown_to_safe_html
        self._old_verifier = draft._verify_body_content
        self._old_p0a_flag = getattr(draft, "_p0a_canonical_persistence_installed", self._missing)
        self._old_run417_flag = getattr(draft, "_run417_body_verification_installed", self._missing)
        run417.install(draft)

    def tearDown(self) -> None:
        draft._markdown_to_safe_html = self._old_renderer
        draft._verify_body_content = self._old_verifier
        for name, old in (
            ("_p0a_canonical_persistence_installed", self._old_p0a_flag),
            ("_run417_body_verification_installed", self._old_run417_flag),
        ):
            if old is self._missing:
                try:
                    delattr(draft, name)
                except AttributeError:
                    pass
            else:
                setattr(draft, name, old)

    def assertCanonicalRejects(self, expected_markdown: str, actual_snapshot: dict) -> None:
        with self.assertRaises(draft.NoteDraftError) as caught:
            draft._verify_body_content(FakeBody(snapshot=actual_snapshot), expected_markdown)
        self.assertEqual("note body canonical persistence verification failed", str(caught.exception))
        self.assertNotIn(expected_markdown, str(caught.exception))

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

        self.assertEqual("note body canonical persistence verification failed", str(caught.exception))
        self.assertNotIn("99秒", str(caught.exception))
        self.assertNotIn(expected, str(caught.exception))

    def test_effective_cloud_verifier_fails_closed_on_unknown_dom_wrapper(self) -> None:
        expected = "本文" * 120
        self.assertCanonicalRejects(expected, root(el("section", [text(expected)])))

    def test_effective_cloud_verifier_rejects_c23_semantic_and_structural_mutations(self) -> None:
        cases = {
            "negation": (
                "この機能は有効です。",
                root(el("p", [text("この機能は有効ではありません。")])),
            ),
            "number": (
                "処理時間は10秒です。",
                root(el("p", [text("処理時間は99秒です。")])),
            ),
            "unit": (
                "処理時間は10秒です。",
                root(el("p", [text("処理時間は10年です。")])),
            ),
            "entity": (
                "Product Aを採用する。",
                root(el("p", [text("Product Bを採用する。")])),
            ),
            "href": (
                "[公式](https://example.com/a)",
                root(el("p", [el("a", [text("公式")], href="https://example.com/b")])),
            ),
            "list_order": (
                "- Alpha\n- Beta",
                root(el("ul", [el("li", [text("Beta")]), el("li", [text("Alpha")])])),
            ),
            "list_start": (
                "3. Alpha\n4. Beta",
                root(el("ol", [el("li", [text("Alpha")]), el("li", [text("Beta")])], start="1")),
            ),
            "heading_level": (
                "## 重要",
                root(el("h3", [text("重要")])),
            ),
            "inline_code": (
                "値は `x=1` です。",
                root(el("p", [text("値は "), el("code", [text("x=2")]), text(" です。")])),
            ),
            "code_whitespace": (
                "```\n  x = 1  \n\nend\n```",
                root(el("pre", [el("code", [text(" x = 1\n\nend")])])),
            ),
        }
        for name, (expected, actual) in cases.items():
            with self.subTest(name=name):
                self.assertCanonicalRejects(expected, actual)

    def test_effective_cloud_renderer_rejects_unsupported_source_without_echoing_content(self) -> None:
        private_source = "# PRIVATE-H1-SENTINEL\n\n本文"
        with self.assertRaises(draft.NoteDraftError) as caught:
            draft._markdown_to_safe_html(private_source)
        self.assertEqual("note manuscript violates the canonical document contract", str(caught.exception))
        self.assertNotIn("PRIVATE-H1-SENTINEL", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
