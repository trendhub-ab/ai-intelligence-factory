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


def li_paragraph(value: str) -> dict:
    return el("li", [el("p", [text(value)])])


def test_real_note_li_paragraph_shape_stays_fail_closed_without_explicit_normalization() -> None:
    snapshot = root(el("ul", [li_paragraph("A")]))
    with pytest.raises(contract.CanonicalContractError) as exc:
        dom.document_from_note_snapshot(snapshot)
    assert exc.value.code == "unsupported_note_dom"


def test_explicit_proven_normalization_unwraps_single_paragraph_inside_unordered_list_item() -> None:
    snapshot = root(el("ul", [li_paragraph("A"), li_paragraph("B")]))
    actual = dom.document_from_note_snapshot(
        snapshot,
        allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
    )
    expected = contract.parse_presentation_markdown("- A\n- B")
    assert contract.compare_documents(expected, actual)["canonical_match"] is True


def test_explicit_proven_normalization_preserves_ordered_list_start_and_inline_semantics() -> None:
    snapshot = root(
        el(
            "ol",
            [
                el("li", [el("p", [text("A "), el("strong", [text("重要")])])]),
                li_paragraph("B"),
            ],
            start="3",
        )
    )
    actual = dom.document_from_note_snapshot(
        snapshot,
        allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
    )
    expected = contract.parse_presentation_markdown("3. A **重要**\n4. B")
    assert contract.compare_documents(expected, actual)["canonical_match"] is True


@pytest.mark.parametrize(
    "item",
    [
        el("li", [el("p", [text("A")]), el("p", [text("B")])]),
        el("li", [text("A"), el("p", [text("B")])]),
        el("li", [el("p", [text("A")], role="presentation")]),
        el("li", [el("h2", [text("A")])]),
    ],
)
def test_proven_normalization_rejects_ambiguous_or_unobserved_list_item_shapes(item: dict) -> None:
    snapshot = root(el("ul", [item]))
    with pytest.raises(contract.CanonicalContractError) as exc:
        dom.document_from_note_snapshot(
            snapshot,
            allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
        )
    assert exc.value.code == "unsupported_note_dom"


def test_unknown_normalization_code_remains_fail_closed() -> None:
    snapshot = root(el("ul", [li_paragraph("A")]))
    with pytest.raises(contract.CanonicalContractError) as exc:
        dom.document_from_note_snapshot(snapshot, allowed_normalizations=("unproven-rule",))
    assert exc.value.code == "unsupported_normalization"


def test_normalization_policy_version_advances_when_real_note_rule_is_enabled() -> None:
    assert contract.NORMALIZATION_POLICY_VERSION == "p0a-normalization-v2"


def test_run292_canonical_verifier_enables_only_the_proven_normalization() -> None:
    import run292_note_rendered_body_audit as audit292

    snapshot = root(el("ul", [li_paragraph("A"), li_paragraph("B")]))
    metrics = audit292._canonical_snapshot_metrics(snapshot, "- A\n- B")
    assert metrics["canonical_match"] is True
    assert metrics["normalization_policy_version"] == "p0a-normalization-v2"
