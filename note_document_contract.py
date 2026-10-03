from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable, Tuple
from urllib.parse import urlparse

CONTRACT_VERSION = "p0a-canonical-v1"
NORMALIZATION_POLICY_VERSION = "p0a-normalization-v1"


class CanonicalContractError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Text:
    value: str


@dataclass(frozen=True)
class HardBreak:
    pass


@dataclass(frozen=True)
class InlineCode:
    text: str


@dataclass(frozen=True)
class Link:
    href: str
    children: tuple[Any, ...]


@dataclass(frozen=True)
class Strong:
    children: tuple[Any, ...]


@dataclass(frozen=True)
class Emphasis:
    children: tuple[Any, ...]


@dataclass(frozen=True)
class Paragraph:
    children: tuple[Any, ...]


@dataclass(frozen=True)
class Heading:
    level: int
    children: tuple[Any, ...]


@dataclass(frozen=True)
class ListItem:
    children: tuple[Any, ...]


@dataclass(frozen=True)
class OrderedList:
    start: int
    items: tuple[ListItem, ...]


@dataclass(frozen=True)
class UnorderedList:
    items: tuple[ListItem, ...]


@dataclass(frozen=True)
class CodeBlock:
    text: str
    language_metadata: str | None = None


@dataclass(frozen=True)
class BlockQuote:
    children: tuple[Any, ...]


@dataclass(frozen=True)
class Divider:
    pass


@dataclass(frozen=True)
class Document:
    children: tuple[Any, ...]


_INLINE_TOKEN = re.compile(r"`[^`]+`|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|\[[^\]]+\]\([^\s)]+\)")
_LINK_LIKE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_INTERNAL_MARKERS = ("[ARTICLE]", "【ARTICLE】")


def _inline(text: str) -> tuple[Any, ...]:
    # Markdown-looking links with unsupported destinations must fail closed.
    for match in _LINK_LIKE.finditer(text):
        target = match.group(1)
        if not target.startswith(("http://", "https://")):
            raise CanonicalContractError("unsupported_markdown")

    out: list[Any] = []
    pos = 0
    for match in _INLINE_TOKEN.finditer(text):
        if match.start() > pos:
            out.append(Text(text[pos:match.start()]))
        token = match.group(0)
        if token.startswith("`"):
            out.append(InlineCode(token[1:-1]))
        elif token.startswith("**"):
            out.append(Strong(_inline(token[2:-2])))
        elif token.startswith("*"):
            out.append(Emphasis(_inline(token[1:-1])))
        elif token.startswith("["):
            label, href = re.fullmatch(r"\[([^\]]+)\]\(([^\s)]+)\)", token).groups()
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise CanonicalContractError("unsupported_markdown")
            out.append(Link(href, _inline(label)))
        pos = match.end()
    if pos < len(text):
        out.append(Text(text[pos:]))
    return tuple(out)


def _paragraph(lines: list[str]) -> Paragraph:
    children: list[Any] = []
    for index, line in enumerate(lines):
        if index:
            children.append(HardBreak())
        children.extend(_inline(line))
    return Paragraph(tuple(children))


def parse_presentation_markdown(markdown_text: str) -> Document:
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    nodes: list[Any] = []
    paragraph: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            nodes.append(_paragraph(paragraph))
            paragraph = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            i += 1
            continue

        # Any body-level H1 or heading deeper than H4 is outside the note presentation contract.
        heading_any = re.match(r"^\s*(#{1,})\s+(.+?)\s*$", line)
        if heading_any:
            flush_paragraph()
            level = len(heading_any.group(1))
            if level not in {2, 3, 4}:
                raise CanonicalContractError("unsupported_markdown")
            nodes.append(Heading(level, _inline(heading_any.group(2))))
            i += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            if stripped != "```":
                # Language metadata is contract material and is not yet proven preservable.
                raise CanonicalContractError("unsupported_markdown")
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and lines[i].strip() != "```":
                code_lines.append(lines[i])
                i += 1
            if i >= len(lines):
                raise CanonicalContractError("unsupported_markdown")
            nodes.append(CodeBlock("\n".join(code_lines), None))
            i += 1
            continue

        if re.fullmatch(r"\s*-{3,}\s*", line):
            flush_paragraph()
            nodes.append(Divider())
            i += 1
            continue

        if re.match(r"^\s+[-*]\s+", line) or re.match(r"^\s+\d+[.)]\s+", line):
            raise CanonicalContractError("unsupported_markdown")

        unordered = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^(\d+)[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            kind = "ul" if unordered else "ol"
            items: list[ListItem] = []
            start: int | None = None
            expected_number: int | None = None
            while i < len(lines):
                current = lines[i]
                if re.match(r"^\s+[-*]\s+", current) or re.match(r"^\s+\d+[.)]\s+", current):
                    raise CanonicalContractError("unsupported_markdown")
                u = re.match(r"^[-*]\s+(.+)$", current)
                o = re.match(r"^(\d+)[.)]\s+(.+)$", current)
                if kind == "ul" and u:
                    items.append(ListItem(_inline(u.group(1))))
                    i += 1
                    continue
                if kind == "ol" and o:
                    number = int(o.group(1))
                    if start is None:
                        start = number
                        expected_number = number
                    if number != expected_number:
                        raise CanonicalContractError("unsupported_markdown")
                    items.append(ListItem(_inline(o.group(2))))
                    expected_number += 1
                    i += 1
                    continue
                # A different list kind without a blank separator is ambiguous and rejected.
                if u or o:
                    raise CanonicalContractError("unsupported_markdown")
                break
            if kind == "ul":
                nodes.append(UnorderedList(tuple(items)))
            else:
                nodes.append(OrderedList(start or 1, tuple(items)))
            continue

        quote = re.match(r"^>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            nodes.append(BlockQuote(_inline(quote.group(1))))
            i += 1
            continue

        paragraph.append(line)
        i += 1

    flush_paragraph()
    return Document(tuple(nodes))


def _normalize_node(node: Any) -> Any:
    if isinstance(node, Text):
        return Text(unicodedata.normalize("NFC", node.value))
    if isinstance(node, InlineCode):
        return node
    if isinstance(node, Link):
        return Link(node.href, tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, Strong):
        return Strong(tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, Emphasis):
        return Emphasis(tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, Paragraph):
        return Paragraph(tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, Heading):
        return Heading(node.level, tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, ListItem):
        return ListItem(tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, OrderedList):
        return OrderedList(node.start, tuple(_normalize_node(x) for x in node.items))
    if isinstance(node, UnorderedList):
        return UnorderedList(tuple(_normalize_node(x) for x in node.items))
    if isinstance(node, BlockQuote):
        return BlockQuote(tuple(_normalize_node(x) for x in node.children))
    if isinstance(node, Document):
        return Document(tuple(_normalize_node(x) for x in node.children))
    return node


def normalize_document(document: Document, *, normalization_codes: tuple[str, ...] = ()) -> Document:
    if normalization_codes:
        # No note-specific normalization is evidence-backed in Task 1.
        raise CanonicalContractError("unsupported_normalization")
    return _normalize_node(document)


def _contains_marker(node: Any) -> bool:
    if isinstance(node, Text):
        return any(marker in node.value for marker in _INTERNAL_MARKERS)
    for attr in ("children", "items"):
        value = getattr(node, attr, None)
        if value and any(_contains_marker(x) for x in value):
            return True
    return False


def _mismatch(expected: Any, actual: Any, path: str = "document") -> tuple[str, str] | None:
    if type(expected) is not type(actual):
        return "node_type_mismatch", path
    if isinstance(expected, Text):
        if expected.value != actual.value:
            return "text_value_mismatch", path
        return None
    if isinstance(expected, InlineCode):
        return None if expected.text == actual.text else ("text_value_mismatch", path)
    if isinstance(expected, CodeBlock):
        if expected.language_metadata != actual.language_metadata or expected.text != actual.text:
            return "code_mismatch", path
        return None
    if isinstance(expected, Link):
        if expected.href != actual.href:
            return "link_href_mismatch", path
    if isinstance(expected, Heading) and expected.level != actual.level:
        return "heading_level_mismatch", path
    if isinstance(expected, OrderedList) and expected.start != actual.start:
        return "list_start_mismatch", path

    if isinstance(expected, (Document, Paragraph, Heading, Strong, Emphasis, Link, BlockQuote, ListItem)):
        exp_children = expected.children
        act_children = actual.children
        if len(exp_children) != len(act_children):
            return "child_count_mismatch", path
        for idx, (left, right) in enumerate(zip(exp_children, act_children)):
            found = _mismatch(left, right, f"{path}.children[{idx}]")
            if found:
                return found
        return None

    if isinstance(expected, (OrderedList, UnorderedList)):
        if len(expected.items) != len(actual.items):
            return "list_item_count_mismatch", path
        for idx, (left, right) in enumerate(zip(expected.items, actual.items)):
            found = _mismatch(left, right, f"{path}.items[{idx}]")
            if found:
                return found
        return None

    # HardBreak / Divider are equal by type alone.
    return None


def compare_documents(expected: Document, actual: Document) -> dict[str, object]:
    left = normalize_document(expected)
    right = normalize_document(actual)
    if _contains_marker(right) and not _contains_marker(left):
        mismatch = ("internal_marker_mismatch", "document")
    else:
        mismatch = _mismatch(left, right)
    return {
        "canonical_match": mismatch is None,
        "mismatch_category": mismatch[0] if mismatch else None,
        "mismatch_path": mismatch[1] if mismatch else None,
        "contract_version": CONTRACT_VERSION,
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
    }

import html as _html
from html.parser import HTMLParser


def _render_inline_nodes(children: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for node in children:
        if isinstance(node, Text):
            parts.append(_html.escape(node.value, quote=False))
        elif isinstance(node, HardBreak):
            parts.append('<br>')
        elif isinstance(node, InlineCode):
            parts.append(f'<code>{_html.escape(node.text, quote=False)}</code>')
        elif isinstance(node, Strong):
            parts.append(f'<strong>{_render_inline_nodes(node.children)}</strong>')
        elif isinstance(node, Emphasis):
            parts.append(f'<em>{_render_inline_nodes(node.children)}</em>')
        elif isinstance(node, Link):
            parsed = urlparse(node.href)
            if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                raise CanonicalContractError('unsupported_safe_html')
            href = _html.escape(node.href, quote=True)
            parts.append(f'<a href="{href}">{_render_inline_nodes(node.children)}</a>')
        else:
            raise CanonicalContractError('unsupported_safe_html')
    return ''.join(parts)


def render_safe_html(document: Document) -> str:
    parts: list[str] = []
    for node in normalize_document(document).children:
        if isinstance(node, Paragraph):
            parts.append(f'<p>{_render_inline_nodes(node.children)}</p>')
        elif isinstance(node, Heading):
            if node.level not in {2, 3, 4}:
                raise CanonicalContractError('unsupported_safe_html')
            parts.append(f'<h{node.level}>{_render_inline_nodes(node.children)}</h{node.level}>')
        elif isinstance(node, UnorderedList):
            body = ''.join(f'<li>{_render_inline_nodes(item.children)}</li>' for item in node.items)
            parts.append(f'<ul>{body}</ul>')
        elif isinstance(node, OrderedList):
            body = ''.join(f'<li>{_render_inline_nodes(item.children)}</li>' for item in node.items)
            parts.append(f'<ol start="{node.start}">{body}</ol>')
        elif isinstance(node, BlockQuote):
            parts.append(f'<blockquote>{_render_inline_nodes(node.children)}</blockquote>')
        elif isinstance(node, Divider):
            parts.append('<hr>')
        elif isinstance(node, CodeBlock):
            if node.language_metadata is not None:
                raise CanonicalContractError('unsupported_safe_html')
            parts.append(f'<pre><code>{_html.escape(node.text, quote=False)}</code></pre>')
        else:
            raise CanonicalContractError('unsupported_safe_html')
    return '\n'.join(parts)


class _CanonicalHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document: list[Any] = []
        self.stack: list[dict[str, Any]] = []

    def _fail(self) -> None:
        raise CanonicalContractError('unsupported_safe_html')

    def _current(self) -> dict[str, Any] | None:
        return self.stack[-1] if self.stack else None

    def _append_node(self, node: Any) -> None:
        current = self._current()
        if current is None:
            self.document.append(node)
            return
        kind = current['kind']
        if kind in {'p', 'heading', 'li', 'blockquote', 'strong', 'em', 'a', 'inline_code'}:
            current['children'].append(node)
            return
        if kind in {'ul', 'ol'} and isinstance(node, ListItem):
            current['items'].append(node)
            return
        self._fail()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = dict(attrs)
        current = self._current()

        if tag in {'p', 'h2', 'h3', 'h4', 'blockquote', 'ul', 'ol', 'pre'}:
            if current is not None:
                self._fail()
            if tag == 'ol':
                if not attr:
                    start = 1
                elif set(attr) == {'start'} and attr.get('start') is not None and str(attr['start']).isdigit():
                    start = int(str(attr['start']))
                else:
                    self._fail()
                self.stack.append({'kind': 'ol', 'start': start, 'items': []})
            elif tag == 'ul':
                if attr:
                    self._fail()
                self.stack.append({'kind': 'ul', 'items': []})
            elif tag == 'pre':
                if attr:
                    self._fail()
                self.stack.append({'kind': 'pre', 'text': [], 'code_open': False})
            elif tag.startswith('h'):
                if attr:
                    self._fail()
                self.stack.append({'kind': 'heading', 'level': int(tag[1]), 'children': []})
            else:
                if attr:
                    self._fail()
                self.stack.append({'kind': tag, 'children': []})
            return

        if tag == 'li':
            if current is None or current['kind'] not in {'ul', 'ol'} or attr:
                self._fail()
            self.stack.append({'kind': 'li', 'children': []})
            return

        if tag == 'code' and current is not None and current['kind'] == 'pre':
            if attr or current['code_open']:
                self._fail()
            current['code_open'] = True
            self.stack.append({'kind': 'pre_code', 'parent': current})
            return

        if tag in {'strong', 'em', 'a', 'code'}:
            if current is None or current['kind'] not in {'p', 'heading', 'li', 'blockquote', 'strong', 'em', 'a'}:
                self._fail()
            if tag == 'a':
                if set(attr) != {'href'} or not attr.get('href'):
                    self._fail()
                href = str(attr['href'])
                parsed = urlparse(href)
                if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                    self._fail()
                self.stack.append({'kind': 'a', 'href': href, 'children': []})
            elif tag == 'code':
                if attr:
                    self._fail()
                self.stack.append({'kind': 'inline_code', 'children': []})
            else:
                if attr:
                    self._fail()
                self.stack.append({'kind': tag, 'children': []})
            return

        if tag == 'br':
            if attrs or current is None or current['kind'] not in {'p', 'heading', 'li', 'blockquote', 'strong', 'em', 'a'}:
                self._fail()
            self._append_node(HardBreak())
            return

        if tag == 'hr':
            if attrs or current is not None:
                self._fail()
            self.document.append(Divider())
            return

        self._fail()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.stack:
            self._fail()
        frame = self.stack[-1]

        if tag == 'code' and frame['kind'] == 'pre_code':
            self.stack.pop()
            frame['parent']['code_open'] = False
            return

        expected = {
            'p': 'p', 'h2': 'heading', 'h3': 'heading', 'h4': 'heading',
            'blockquote': 'blockquote', 'ul': 'ul', 'ol': 'ol', 'li': 'li',
            'strong': 'strong', 'em': 'em', 'a': 'a', 'code': 'inline_code', 'pre': 'pre',
        }.get(tag)
        if expected is None or frame['kind'] != expected:
            self._fail()
        if tag.startswith('h') and frame.get('level') != int(tag[1]):
            self._fail()

        self.stack.pop()
        kind = frame['kind']
        if kind == 'p':
            node = Paragraph(tuple(frame['children']))
        elif kind == 'heading':
            node = Heading(frame['level'], tuple(frame['children']))
        elif kind == 'blockquote':
            node = BlockQuote(tuple(frame['children']))
        elif kind == 'li':
            node = ListItem(tuple(frame['children']))
        elif kind == 'ul':
            node = UnorderedList(tuple(frame['items']))
        elif kind == 'ol':
            node = OrderedList(frame['start'], tuple(frame['items']))
        elif kind == 'strong':
            node = Strong(tuple(frame['children']))
        elif kind == 'em':
            node = Emphasis(tuple(frame['children']))
        elif kind == 'a':
            node = Link(frame['href'], tuple(frame['children']))
        elif kind == 'inline_code':
            if any(not isinstance(x, Text) for x in frame['children']):
                self._fail()
            node = InlineCode(''.join(x.value for x in frame['children']))
        elif kind == 'pre':
            if frame['code_open']:
                self._fail()
            node = CodeBlock(''.join(frame['text']), None)
        else:
            self._fail()
            return
        self._append_node(node)

    def handle_data(self, data: str) -> None:
        if not data:
            return
        current = self._current()
        if current is None:
            if data.strip():
                self._fail()
            return
        if current['kind'] == 'pre_code':
            current['parent']['text'].append(data)
            return
        if current['kind'] == 'pre':
            if data.strip():
                self._fail()
            return
        if current['kind'] in {'p', 'heading', 'li', 'blockquote', 'strong', 'em', 'a', 'inline_code'}:
            current['children'].append(Text(data))
            return
        if data.strip():
            self._fail()


def parse_safe_html(html_text: str) -> Document:
    parser = _CanonicalHTMLParser()
    try:
        parser.feed(str(html_text or ''))
        parser.close()
    except CanonicalContractError:
        raise
    except Exception as exc:
        raise CanonicalContractError('unsupported_safe_html') from exc
    if parser.stack:
        raise CanonicalContractError('unsupported_safe_html')
    return normalize_document(Document(tuple(parser.document)))
