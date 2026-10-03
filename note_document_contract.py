from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any
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
            parsed_match = re.fullmatch(r"\[([^\]]+)\]\(([^\s)]+)\)", token)
            if parsed_match is None:
                raise CanonicalContractError("unsupported_markdown")
            label, href = parsed_match.groups()
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
        return None if expected.value == actual.value else ("text_value_mismatch", path)
    if isinstance(expected, InlineCode):
        return None if expected.text == actual.text else ("text_value_mismatch", path)
    if isinstance(expected, CodeBlock):
        if expected.language_metadata != actual.language_metadata or expected.text != actual.text:
            return "code_mismatch", path
        return None
    if isinstance(expected, Link) and expected.href != actual.href:
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
