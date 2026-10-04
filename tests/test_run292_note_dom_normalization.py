from __future__ import annotations

import run292_note_rendered_body_audit as audit


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def el(tag: str, children=()) -> dict:
    return {"type": "element", "tag": tag, "attrs": {}, "children": list(children)}


def root(*children) -> dict:
    return {"type": "root", "children": list(children)}


def test_run292_accepts_only_the_evidenced_note_blockquote_wrapper_normalization():
    snapshot = root(
        el(
            "figure",
            [
                el("blockquote", [el("p", [text("引用")])]),
                el("figcaption", [el("br")]),
            ],
        )
    )
    metrics = audit._canonical_snapshot_metrics(snapshot, "> 引用")
    assert metrics["canonical_match"] is True
    assert metrics["unsupported_actual_node_count"] == 0
    assert metrics["expected_node_counts"] == metrics["actual_node_counts"]


def test_run292_still_rejects_nonempty_note_blockquote_caption():
    snapshot = root(
        el(
            "figure",
            [
                el("blockquote", [el("p", [text("引用")])]),
                el("figcaption", [text("caption")]),
            ],
        )
    )
    try:
        audit._canonical_snapshot_metrics(snapshot, "> 引用")
    except audit.Run292AuditDiagnosticError as exc:
        assert exc.code == "unsupported_note_dom"
        assert exc.safe_metrics["unsupported_actual_node_count"] == 1
    else:
        raise AssertionError("nonempty caption must remain fail-closed")
