from pathlib import Path

import note_draft_automation as base
import run417_note_body_verification as run417


class Body:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def evaluate(self, script):
        return self.snapshot


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def element(tag: str, children=(), **attrs) -> dict:
    return {"type": "element", "tag": tag, "attrs": attrs, "children": list(children)}


def root(*children) -> dict:
    return {"type": "root", "children": list(children)}


def test_run417_accepts_exact_canonical_paragraph():
    run417.verify_body_content(Body(root(element("p", [text("10秒")]))) , "10秒")


def test_run417_rejects_semantic_mutation_with_content_free_error():
    try:
        run417.verify_body_content(Body(root(element("p", [text("99秒")]))) , "10秒")
    except base.NoteDraftError as exc:
        assert str(exc) == "note body canonical persistence verification failed"
        assert "10秒" not in str(exc)
        assert "99秒" not in str(exc)
    else:
        raise AssertionError("semantic mutation must fail closed")


def test_run417_rejects_unknown_dom_wrapper():
    try:
        run417.verify_body_content(Body(root(element("section", [text("本文")]))) , "本文")
    except base.NoteDraftError as exc:
        assert str(exc) == "note body canonical persistence verification failed"
    else:
        raise AssertionError("unknown note DOM must fail closed")


def test_run417_rejects_code_whitespace_change():
    manuscript = "```\n  x = 1  \n\nend\n```"
    snapshot = root(element("pre", [element("code", [text(" x = 1\n\nend")])]))
    try:
        run417.verify_body_content(Body(snapshot), manuscript)
    except base.NoteDraftError as exc:
        assert str(exc) == "note body canonical persistence verification failed"
    else:
        raise AssertionError("code whitespace corruption must fail closed")


def test_run417_renderer_rejects_unsupported_body_h1_without_echoing_content():
    source = "# PRIVATE-H1-SENTINEL\n\n本文"
    try:
        run417.markdown_to_safe_html(source)
    except base.NoteDraftError as exc:
        assert str(exc) == "note manuscript violates the canonical document contract"
        assert "PRIVATE-H1-SENTINEL" not in str(exc)
    else:
        raise AssertionError("unsupported source syntax must fail closed")


def test_run417_install_replaces_effective_renderer_and_verifier():
    class Module:
        _markdown_to_safe_html = object()
        _verify_body_content = object()

    module = Module()
    run417.install(module)
    assert module._markdown_to_safe_html is run417.markdown_to_safe_html
    assert module._verify_body_content is run417.verify_body_content
    assert module._p0a_canonical_persistence_installed is True
    assert module._run417_body_verification_installed is True


def test_run417_is_zero_model_and_has_no_public_mutation_surface():
    source = Path(run417.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "gemini_api_key",
        "generativelanguage.googleapis.com",
        ".click(",
        ".fill(",
        "publish_article",
        "release_article",
    ):
        assert forbidden not in source
