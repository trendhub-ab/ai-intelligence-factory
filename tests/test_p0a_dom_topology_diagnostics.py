from __future__ import annotations

import note_document_dom as dom


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def el(tag: str, children=(), **attrs) -> dict:
    return {"type": "element", "tag": tag, "attrs": attrs, "children": list(children)}


def root(*children) -> dict:
    return {"type": "root", "children": list(children)}


def test_safe_diagnostics_include_only_element_topology_counts() -> None:
    snapshot = root(
        el("ul", [el("li", [el("p", [text("PRIVATE-LIST-SENTINEL")])])]),
        el("p", [el("strong", [text("PRIVATE-STRONG-SENTINEL")])]),
    )
    result = dom.safe_snapshot_diagnostics(snapshot)
    assert result["dom_parent_child_tag_counts"] == {
        "li>p": 1,
        "p>strong": 1,
        "root>p": 1,
        "root>ul": 1,
        "ul>li": 1,
    }
    rendered = repr(result)
    assert "PRIVATE-LIST-SENTINEL" not in rendered
    assert "PRIVATE-STRONG-SENTINEL" not in rendered


def test_topology_diagnostics_keep_unknown_tag_names_safe() -> None:
    snapshot = root(el("section", [el("p", [text("PRIVATE")])]))
    result = dom.safe_snapshot_diagnostics(snapshot)
    assert result["dom_parent_child_tag_counts"] == {"root>section": 1, "section>p": 1}
    assert "PRIVATE" not in repr(result)
