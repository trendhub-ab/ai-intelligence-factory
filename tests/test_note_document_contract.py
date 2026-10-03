import importlib
import unicodedata
import pytest


def contract():
    try:
        return importlib.import_module('note_document_contract')
    except ModuleNotFoundError:
        pytest.fail('note_document_contract module is not implemented yet')


def test_parses_supported_aiif_markdown_surface():
    c = contract()
    md = (
        '## 見出し\n\n'
        '通常 **重要** *補足* `code` [リンク](https://example.com/a?x=1&y=2)\n'
        '次の行🙂\n\n'
        '- A\n- B\n\n'
        '3. 三\n4. 四\n\n'
        '> 引用\n\n'
        '---\n\n'
        '```\n  x = 1  \n\nprint(x)\n```\n\n'
        '### 小見出し\n\n#### 最小見出し'
    )
    doc = c.parse_presentation_markdown(md)
    assert isinstance(doc, c.Document)
    assert [type(node).__name__ for node in doc.children] == [
        'Heading', 'Paragraph', 'UnorderedList', 'OrderedList', 'BlockQuote',
        'Divider', 'CodeBlock', 'Heading', 'Heading'
    ]
    assert doc.children[0].level == 2
    p = doc.children[1]
    assert isinstance(p, c.Paragraph)
    assert any(isinstance(x, c.Strong) for x in p.children)
    assert any(isinstance(x, c.Emphasis) for x in p.children)
    assert any(isinstance(x, c.InlineCode) and x.text == 'code' for x in p.children)
    link = next(x for x in p.children if isinstance(x, c.Link))
    assert link.href == 'https://example.com/a?x=1&y=2'
    assert any(isinstance(x, c.HardBreak) for x in p.children)
    assert doc.children[3].start == 3
    assert [item.children[0].value for item in doc.children[3].items] == ['三', '四']
    code = doc.children[6]
    assert code.text == '  x = 1  \n\nprint(x)'
    assert code.language_metadata is None
    assert doc.children[7].level == 3
    assert doc.children[8].level == 4


def test_nfc_equivalent_prose_normalizes_but_fullwidth_does_not():
    c = contract()
    decomposed = 'Cafe\u0301'
    composed = unicodedata.normalize('NFC', decomposed)
    left = c.parse_presentation_markdown(f'段落 {decomposed}')
    right = c.parse_presentation_markdown(f'段落 {composed}')
    assert c.compare_documents(left, right)['canonical_match'] is True

    fw = c.parse_presentation_markdown('ＡＩ')
    ascii_doc = c.parse_presentation_markdown('AI')
    receipt = c.compare_documents(fw, ascii_doc)
    assert receipt['canonical_match'] is False
    assert receipt['mismatch_category'] == 'text_value_mismatch'


def test_h1_is_unsupported_after_presentation_transform():
    c = contract()
    with pytest.raises(c.CanonicalContractError) as exc:
        c.parse_presentation_markdown('# body-level H1')
    assert exc.value.code == 'unsupported_markdown'


@pytest.mark.parametrize('md', [
    '1. A\n3. C',
    '- A\n  - nested',
    '- A\n1. B',
    '```python\nprint(1)\n```',
    '[bad](ftp://example.com)',
])
def test_unsupported_or_ambiguous_markdown_fails_closed(md):
    c = contract()
    with pytest.raises(c.CanonicalContractError) as exc:
        c.parse_presentation_markdown(md)
    assert exc.value.code == 'unsupported_markdown'


def test_compare_documents_rejects_semantic_and_structural_mutations_without_content_leak():
    c = contract()
    base = c.parse_presentation_markdown(
        '## 判断\n\n'
        'Product Aは10秒で完了し、比較対象はModel Bです。\n\n'
        '2. 第一\n3. 第二\n\n'
        '[公式](https://example.com/a)\n\n'
        '`tool_choice` を使う。\n\n'
        '> 引用\n\n'
        '```\n  x = 1\n```'
    )
    mutations = {
        'negation': 'Product Aは10秒で完了しません、比較対象はModel Bです。',
        'number': 'Product Aは99秒で完了し、比較対象はModel Bです。',
        'unit': 'Product Aは10年で完了し、比較対象はModel Bです。',
        'entity': 'Product Cは10秒で完了し、比較対象はModel Bです。',
        'comparison': 'Product Aは10秒で完了し、比較対象はModel Zです。',
    }
    original_sentence = 'Product Aは10秒で完了し、比較対象はModel Bです。'
    for name, replacement in mutations.items():
        actual = c.parse_presentation_markdown(
            ('## 判断\n\n' + replacement + '\n\n'
             '2. 第一\n3. 第二\n\n'
             '[公式](https://example.com/a)\n\n'
             '`tool_choice` を使う。\n\n'
             '> 引用\n\n'
             '```\n  x = 1\n```')
        )
        receipt = c.compare_documents(base, actual)
        assert receipt['canonical_match'] is False, name
        assert receipt['mismatch_category'] == 'text_value_mismatch', name
        assert original_sentence not in repr(receipt)
        assert replacement not in repr(receipt)
        assert 'https://example.com/a' not in repr(receipt)


def test_compare_documents_rejects_href_list_heading_inline_code_quote_and_code_mutations():
    c = contract()
    cases = [
        ('[公式](https://example.com/a)', '[公式](https://example.com/b)', 'link_href_mismatch'),
        ('2. A\n3. B', '2. B\n3. A', 'text_value_mismatch'),
        ('2. A\n3. B', '3. A\n4. B', 'list_start_mismatch'),
        ('## H', '### H', 'heading_level_mismatch'),
        ('`x`', 'x', 'node_type_mismatch'),
        ('> Q', 'Q', 'node_type_mismatch'),
        ('```\n x\n```', '```\n  x\n```', 'code_mismatch'),
    ]
    for expected_md, actual_md, category in cases:
        receipt = c.compare_documents(
            c.parse_presentation_markdown(expected_md),
            c.parse_presentation_markdown(actual_md),
        )
        assert receipt['canonical_match'] is False, (expected_md, actual_md)
        assert receipt['mismatch_category'] == category
        assert 'expected_text' not in receipt
        assert 'actual_text' not in receipt
        assert 'href' not in receipt


def test_compare_documents_rejects_item_add_delete_paragraph_duplicate_and_internal_markers():
    c = contract()
    pairs = [
        ('- A\n- B', '- A\n- B\n- C'),
        ('- A\n- B', '- A'),
        ('one\n\ntwo', 'one\n\ntwo\n\ntwo'),
        ('本文', '本文\n\n[ARTICLE]'),
        ('本文', '本文\n\n【ARTICLE】'),
    ]
    for expected_md, actual_md in pairs:
        receipt = c.compare_documents(
            c.parse_presentation_markdown(expected_md),
            c.parse_presentation_markdown(actual_md),
        )
        assert receipt['canonical_match'] is False
        assert receipt['mismatch_category'] in {
            'child_count_mismatch', 'list_item_count_mismatch', 'internal_marker_mismatch'
        }


def test_versions_are_present_and_receipt_is_content_free_on_match():
    c = contract()
    assert isinstance(c.CONTRACT_VERSION, str) and c.CONTRACT_VERSION
    assert isinstance(c.NORMALIZATION_POLICY_VERSION, str) and c.NORMALIZATION_POLICY_VERSION
    doc = c.parse_presentation_markdown('本文')
    receipt = c.compare_documents(doc, doc)
    assert receipt == {
        'canonical_match': True,
        'mismatch_category': None,
        'mismatch_path': None,
        'contract_version': c.CONTRACT_VERSION,
        'normalization_policy_version': c.NORMALIZATION_POLICY_VERSION,
    }
