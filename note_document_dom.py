from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import note_document_contract as contract


_SNAPSHOT_SCRIPT = r"""el => {
  const walk = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      return {type: 'text', text: node.textContent || ''};
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return null;
    const tag = node.tagName.toLowerCase();
    const attrs = {};
    if (tag === 'a') attrs.href = node.getAttribute('href') || '';
    if (tag === 'ol' && node.hasAttribute('start')) attrs.start = node.getAttribute('start') || '';
    const children = [];
    for (const child of node.childNodes) {
      const mapped = walk(child);
      if (mapped) children.push(mapped);
    }
    return {type: 'element', tag, attrs, children};
  };
  const children = [];
  for (const child of el.childNodes) {
    const mapped = walk(child);
    if (mapped) children.push(mapped);
  }
  return {type: 'root', children};
}"""


def snapshot_note_body(body_locator: object) -> dict[str, object]:
    value = body_locator.evaluate(_SNAPSHOT_SCRIPT)
    if not isinstance(value, dict):
        raise contract.CanonicalContractError('unsupported_note_dom')
    return value


def _fail() -> None:
    raise contract.CanonicalContractError('unsupported_note_dom')


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    value = node.get('children')
    if not isinstance(value, list):
        _fail()
    if not all(isinstance(item, dict) for item in value):
        _fail()
    return value


def _attrs(node: dict[str, Any]) -> dict[str, Any]:
    value = node.get('attrs', {})
    if not isinstance(value, dict):
        _fail()
    return value


def _text_node(node: dict[str, Any]) -> contract.Text:
    if node.get('type') != 'text' or not isinstance(node.get('text'), str):
        _fail()
    return contract.Text(node['text'])


def _inline_nodes(nodes: list[dict[str, Any]]) -> tuple[Any, ...]:
    result: list[Any] = []
    for node in nodes:
        node_type = node.get('type')
        if node_type == 'text':
            result.append(_text_node(node))
            continue
        if node_type != 'element':
            _fail()
        tag = str(node.get('tag') or '').lower()
        attrs = _attrs(node)
        kids = _children(node)
        if tag == 'br':
            if attrs or kids:
                _fail()
            result.append(contract.HardBreak())
        elif tag == 'strong':
            if attrs:
                _fail()
            result.append(contract.Strong(_inline_nodes(kids)))
        elif tag == 'em':
            if attrs:
                _fail()
            result.append(contract.Emphasis(_inline_nodes(kids)))
        elif tag == 'code':
            if attrs or any(child.get('type') != 'text' for child in kids):
                _fail()
            result.append(contract.InlineCode(''.join(_text_node(child).value for child in kids)))
        elif tag == 'a':
            if set(attrs) != {'href'} or not isinstance(attrs.get('href'), str):
                _fail()
            href = attrs['href']
            parsed = urlparse(href)
            if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                _fail()
            result.append(contract.Link(href, _inline_nodes(kids)))
        else:
            _fail()
    return tuple(result)


def _list_item(node: dict[str, Any]) -> contract.ListItem:
    if node.get('type') != 'element' or str(node.get('tag') or '').lower() != 'li' or _attrs(node):
        _fail()
    return contract.ListItem(_inline_nodes(_children(node)))


def _block(node: dict[str, Any]) -> Any:
    if node.get('type') != 'element':
        _fail()
    tag = str(node.get('tag') or '').lower()
    attrs = _attrs(node)
    kids = _children(node)

    if tag == 'p':
        if attrs:
            _fail()
        return contract.Paragraph(_inline_nodes(kids))
    if tag in {'h2', 'h3', 'h4'}:
        if attrs:
            _fail()
        return contract.Heading(int(tag[1]), _inline_nodes(kids))
    if tag == 'blockquote':
        if attrs:
            _fail()
        return contract.BlockQuote(_inline_nodes(kids))
    if tag == 'hr':
        if attrs or kids:
            _fail()
        return contract.Divider()
    if tag == 'ul':
        if attrs:
            _fail()
        return contract.UnorderedList(tuple(_list_item(child) for child in kids))
    if tag == 'ol':
        if not attrs:
            start = 1
        elif set(attrs) == {'start'} and isinstance(attrs.get('start'), str) and attrs['start'].isdigit():
            start = int(attrs['start'])
        else:
            _fail()
        return contract.OrderedList(start, tuple(_list_item(child) for child in kids))
    if tag == 'pre':
        if attrs or len(kids) != 1:
            _fail()
        code = kids[0]
        if code.get('type') != 'element' or str(code.get('tag') or '').lower() != 'code' or _attrs(code):
            _fail()
        code_children = _children(code)
        if any(child.get('type') != 'text' for child in code_children):
            _fail()
        return contract.CodeBlock(''.join(_text_node(child).value for child in code_children), None)
    _fail()


def document_from_note_snapshot(
    snapshot: dict[str, object], *, allowed_normalizations: tuple[str, ...] = ()
) -> contract.Document:
    if not isinstance(snapshot, dict) or snapshot.get('type') != 'root':
        _fail()
    children = snapshot.get('children')
    if not isinstance(children, list):
        _fail()
    blocks: list[Any] = []
    for child in children:
        if not isinstance(child, dict):
            _fail()
        if child.get('type') == 'text':
            value = child.get('text')
            if not isinstance(value, str) or value.strip():
                _fail()
            continue
        blocks.append(_block(child))
    return contract.normalize_document(contract.Document(tuple(blocks)), normalization_codes=allowed_normalizations)
