from __future__ import annotations

import pytest

import note_document_contract as contract
import note_document_dom as dom


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def el(tag: str, children=(), **attrs) -> dict:
    return {"type": "element", "tag": tag, "attrs": attrs, "children": list(children)}


def root(*children) -> dict:
    return {"type": "root", "children": list(children)}


def test_unordered_list_single_paragraph_wrapper_is_semantically_transparent() -> None:
    wrapped = root(
        el("ul", [
            el("li", [el("p", [text("A "), el("strong", [text("重要")])])]),
            el("li", [el("p", [text("B "), el("a", [text("公式")], href="https://example.com/b")])]),
        ])
    )
    direct = root(
        el("ul", [
            el("li", [text("A "), el("strong", [text("重要")])]),
            el("li", [text("B "), el("a", [text("公式")], href="https://example.com/b")]),
        ])
    )
    wrapped_doc = dom.document_from_note_snapshot(wrapped)
    direct_doc = dom.document_from_note_snapshot(direct)
    assert contract.compare_documents(direct_doc, wrapped_doc)["canonical_match"] is True


def test_ordered_list_single_paragraph_wrapper_preserves_start_and_inline_semantics() -> None:
    snap = root(
        el("ol", [
            el("li", [el("p", [text("Item "), el("strong", [text("one")])])]),
            el("li", [el("p", [text("Item two")])]),
        ], start="3")
    )
    actual = dom.document_from_note_snapshot(snap)
    expected = contract.parse_presentation_markdown("3. Item **one**\n4. Item two")
    assert contract.compare_documents(expected, actual)["canonical_match"] is True


@pytest.mark.parametrize(
    "item_children",
    [
        [el("p", [text("A")]), el("p", [text("B")])],
        [text("prefix"), el("p", [text("A")])],
        [el("p", [text("A")]), text("suffix")],
        [el("p", [text("A")], class_="unexpected")],
        [el("p", [el("ul", [el("li", [text("nested")])])])],
    ],
)
def test_unproven_list_item_block_shapes_remain_fail_closed(item_children) -> None:
    snap = root(el("ul", [el("li", item_children)]))
    with pytest.raises(contract.CanonicalContractError) as exc:
        dom.document_from_note_snapshot(snap)
    assert exc.value.code == "unsupported_note_dom"


def test_existing_direct_inline_list_item_contract_remains_supported() -> None:
    snap = root(el("ul", [el("li", [text("A"), el("strong", [text("B")])])]))
    doc = dom.document_from_note_snapshot(snap)
    expected = contract.parse_presentation_markdown("- A**B**")
    assert contract.compare_documents(expected, doc)["canonical_match"] is True
