import inspect
import importlib
import pytest


def dommod():
    try:
        return importlib.import_module('note_document_dom')
    except ModuleNotFoundError:
        pytest.fail('note_document_dom module is not implemented yet')


def contract():
    return importlib.import_module('note_document_contract')


class FakeLocator:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0
        self.script = ''

    def evaluate(self, script):
        self.calls += 1
        self.script = script
        return self.snapshot


def el(tag, children=(), **attrs):
    return {'type': 'element', 'tag': tag, 'attrs': attrs, 'children': list(children)}


def text(value):
    return {'type': 'text', 'text': value}


def root(*children):
    return {'type': 'root', 'children': list(children)}


def test_snapshot_note_body_uses_one_read_only_evaluate_and_returns_transient_tree():
    d = dommod()
    snapshot = root(el('p', [text('本文')]))
    locator = FakeLocator(snapshot)
    assert d.snapshot_note_body(locator) == snapshot
    assert locator.calls == 1
    assert 'outerHTML' not in locator.script
    assert 'innerHTML' not in locator.script
    assert 'textContent' in locator.script


def test_document_from_note_snapshot_maps_supported_semantic_structure():
    d = dommod()
    c = contract()
    snap = root(
        el('h2', [text('見出し')]),
        el('p', [text('本文 '), el('strong', [text('重要')]), text(' '), el('em', [text('補足')]),
                 text(' '), el('code', [text('x')]), text(' '),
                 el('a', [text('公式')], href='https://example.com/a'), el('br'), text('次行')]),
        el('ul', [el('li', [text('A')]), el('li', [text('B')])]),
        el('ol', [el('li', [text('C')]), el('li', [text('D')])], start='3'),
        el('blockquote', [text('引用')]),
        el('hr'),
        el('pre', [el('code', [text('  x = 1  \n\nend')])]),
    )
    doc = d.document_from_note_snapshot(snap)
    expected = c.parse_presentation_markdown(
        '## 見出し\n\n本文 **重要** *補足* `x` [公式](https://example.com/a)\n次行\n\n'
        '- A\n- B\n\n3. C\n4. D\n\n> 引用\n\n---\n\n```\n  x = 1  \n\nend\n```'
    )
    assert c.compare_documents(expected, doc)['canonical_match'] is True


def test_ordered_list_missing_start_uses_html_default_one():
    d = dommod()
    c = contract()
    doc = d.document_from_note_snapshot(root(el('ol', [el('li', [text('A')]), el('li', [text('B')])])) )
    assert isinstance(doc.children[0], c.OrderedList)
    assert doc.children[0].start == 1


@pytest.mark.parametrize('snap', [
    root(el('div', [el('p', [text('wrapper')])])),
    root(el('section', [el('p', [text('x')])])),
    root(el('a', [text('x')], href='https://example.com/a')),
    root(el('p', [el('a', [text('x')])])),
    root(el('p', [el('a', [text('x')], href='javascript:alert(1)')])),
    root(el('h1', [text('bad')])),
])
def test_unknown_or_ambiguous_note_dom_fails_closed(snap):
    d = dommod()
    c = contract()
    with pytest.raises(c.CanonicalContractError) as exc:
        d.document_from_note_snapshot(snap)
    assert exc.value.code == 'unsupported_note_dom'


def test_unknown_wrapper_diagnostics_are_structural_and_content_free():
    d = dommod()
    snap = root(
        el(
            'div',
            [
                el('p', [text('PRIVATE-BODY-SENTINEL')]),
                el('section', [text('PRIVATE-TITLE-SENTINEL')]),
                el('a', [text('PRIVATE-LINK-LABEL')], href='https://private.example/secret-path'),
            ],
            title='PRIVATE-ATTR-SENTINEL',
        )
    )
    diagnostics = d.safe_snapshot_diagnostics(snap)
    assert diagnostics['dom_diagnostic_category'] == 'unknown_dom_tag'
    assert diagnostics['unknown_dom_tags'] == ['div', 'section']
    assert diagnostics['unknown_dom_tag_counts'] == {'div': 1, 'section': 1}
    assert diagnostics['dom_tag_counts'] == {'a': 1, 'div': 1, 'p': 1, 'section': 1}
    assert diagnostics['snapshot_element_node_count'] == 4
    assert diagnostics['snapshot_text_node_count'] == 3
    assert diagnostics['snapshot_total_node_count'] == 7
    rendered = repr(diagnostics)
    for forbidden in (
        'PRIVATE-BODY-SENTINEL', 'PRIVATE-TITLE-SENTINEL', 'PRIVATE-LINK-LABEL',
        'PRIVATE-ATTR-SENTINEL', 'private.example', 'secret-path',
    ):
        assert forbidden not in rendered


def test_supported_tag_but_invalid_dom_shape_has_fixed_content_free_category():
    d = dommod()
    diagnostics = d.safe_snapshot_diagnostics(
        root(el('a', [text('PRIVATE-BODY-SENTINEL')], href='https://private.example/secret-path'))
    )
    assert diagnostics['dom_diagnostic_category'] == 'unsupported_dom_shape'
    assert diagnostics['unknown_dom_tags'] == []
    assert diagnostics['unknown_dom_tag_counts'] == {}
    assert diagnostics['dom_tag_counts'] == {'a': 1}
    assert 'PRIVATE-BODY-SENTINEL' not in repr(diagnostics)
    assert 'private.example' not in repr(diagnostics)


def test_semantic_dom_mutations_are_visible_to_canonical_comparator():
    d = dommod()
    c = contract()
    expected = c.parse_presentation_markdown('## H\n\n10秒 Product A [公式](https://example.com/a)')
    cases = [
        (root(el('h2', [text('H')]), el('p', [text('99秒 Product A '), el('a', [text('公式')], href='https://example.com/a')])), 'text_value_mismatch'),
        (root(el('h2', [text('H')]), el('p', [text('10年 Product A '), el('a', [text('公式')], href='https://example.com/a')])), 'text_value_mismatch'),
        (root(el('h2', [text('H')]), el('p', [text('10秒 Product B '), el('a', [text('公式')], href='https://example.com/a')])), 'text_value_mismatch'),
        (root(el('h2', [text('H')]), el('p', [text('10秒 Product A '), el('a', [text('公式')], href='https://example.com/b')])), 'link_href_mismatch'),
    ]
    for snap, category in cases:
        actual = d.document_from_note_snapshot(snap)
        receipt = c.compare_documents(expected, actual)
        assert receipt['canonical_match'] is False
        assert receipt['mismatch_category'] == category
        assert '99秒' not in repr(receipt)
        assert 'https://example.com/b' not in repr(receipt)


def test_dom_adapter_source_has_no_mutation_or_output_surface():
    d = dommod()
    source = inspect.getsource(d)
    for forbidden in (
        '.click(', '.fill(', 'keyboard.', 'dispatch_event', 'ClipboardEvent',
        'screenshot(', 'requests.post(', 'requests.patch(', 'print(', 'open(', 'write_text(',
    ):
        assert forbidden not in source
