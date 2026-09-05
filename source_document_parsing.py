"""Deterministic source-document parsing helpers extracted from pipeline.py (Run242).

Stdlib-only. This module performs no HTTP requests, provider calls, persistence, or quality-gate
execution. Network acquisition remains in pipeline.py; this module only parses already-available
URLs/text and shapes evidence metadata.
"""

import re
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse


def github_repo_name_from_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return ""
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"github.com", "www.github.com"}:
        return ""
    parts = [x for x in (parsed.path or "").split("/") if x]
    if len(parts) < 2:
        return ""
    if parts[0].lower() in {"features", "enterprise", "pricing", "solutions", "marketplace", "topics", "collections", "sponsors", "login", "signup", "settings", "organizations"}:
        return ""
    return f"{parts[0]}/{parts[1]}"


def github_repo_identity(repo: dict, *, repo_name_from_url: Callable[[str], str]) -> str:
    entity_id = str(repo.get("canonicalEntityId") or repo.get("canonical_entity_id") or "")
    if entity_id.lower().startswith("github:") and "/" in entity_id.split(":", 1)[1]:
        return entity_id.split(":", 1)[1]
    for value in (repo.get("primaryUrl"), repo.get("url")):
        name = repo_name_from_url(str(value or ""))
        if name:
            return name
    name = str(repo.get("nameWithOwner") or "").strip()
    return name if "/" in name and not name.startswith(("http://", "https://")) else ""


def is_github_global_navigation_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"github.com", "www.github.com"}:
        return False
    path = (parsed.path or "/").lower()
    blocked = (
        "/features/", "/enterprise", "/pricing", "/solutions/", "/marketplace",
        "/topics/", "/collections/", "/sponsors", "/login", "/signup", "/settings",
        "/organizations/enterprise", "/customer-stories/",
    )
    return any(path == x.rstrip("/") or path.startswith(x) for x in blocked)


def extract_markdown_evidence_links(
    text: str, *, is_global_navigation_url: Callable[[str], bool]
) -> list[tuple[str, str]]:
    if not text:
        return []
    keywords = re.compile(r"\b(?:docs?|documentation|guide|reference|api|website|homepage|source\s*code|repository|github)\b", re.I)
    out: list[tuple[str, str]] = []
    for match in re.finditer(r"(?<!!)\[([^\]]{1,120})\]\((https?://[^\s\)]+)", text):
        label, url = match.group(1).strip(), urldefrag(match.group(2).strip())[0]
        if not keywords.search(label) and not keywords.search(urlparse(url).path or ""):
            continue
        host = (urlparse(url).netloc or "").lower()
        if any(x in host for x in ("shields.io", "badge", "twitter.com", "x.com", "discord.gg", "linkedin.com")):
            continue
        if is_global_navigation_url(url):
            continue
        out.append((url, label))
    return list(dict.fromkeys(out))[:12]


def effective_evidence_source(
    repo: dict,
    *,
    repo_name_from_url: Callable[[str], str],
    extract_arxiv_id: Callable[[str], str],
) -> str:
    entity_id = str(repo.get("canonicalEntityId") or repo.get("canonical_entity_id") or "").lower()
    primary = str(repo.get("primaryUrl") or repo.get("url") or "")
    if entity_id.startswith("github:") or repo_name_from_url(primary):
        return "GitHub"
    if entity_id.startswith("arxiv:") or extract_arxiv_id(primary):
        return "ArXiv"
    return str(repo.get("source") or "GitHub")


def is_redundant_arxiv_doi(url: str, arxiv_id: str) -> bool:
    if not arxiv_id:
        return False
    parsed = urlparse(url or "")
    if (parsed.netloc or "").lower() not in {"doi.org", "dx.doi.org"}:
        return False
    return f"arxiv.{arxiv_id}" in (parsed.path or "").lower()


class ReadableHTMLTextParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
    _BREAK_TAGS = {"title", "h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre", "article", "main", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in self._BREAK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and data:
            self._parts.append(data)

    def text(self) -> str:
        raw = unescape(" ".join(self._parts))
        lines = []
        previous = None
        for line in raw.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if not line or line == previous:
                continue
            if len(line) < 2:
                continue
            lines.append(line)
            previous = line
        return "\n".join(lines)


def is_low_value_arxiv_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        return False
    path = (parsed.path or "/").rstrip("/") or "/"
    lowered = path.lower()
    if lowered == "/":
        return True
    blocked_prefixes = (
        "/prevnext", "/ignoreme", "/search", "/list", "/help",
        "/login", "/format", "/catchup", "/multi", "/show-email",
    )
    return lowered.startswith(blocked_prefixes)


class ResearchLinkParser(HTMLParser):
    _KEYWORDS = re.compile(r"\b(pdf|paper|publication|full\s*paper|download|proceedings|doi|supplement|appendix|technical\s*report|docs?|documentation|github|gitlab|repository|source\s*code)\b", re.I)

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href", "")
            self._current_href = urljoin(self.base_url, href) if href else ""
            self._current_text = []

    def handle_data(self, data):
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._current_href:
            return
        href = urldefrag(self._current_href)[0]
        label = " ".join(self._current_text).strip()
        parsed = urlparse(href)
        href_signal = f"{parsed.path}?{parsed.query}"
        if (
            href.startswith(("http://", "https://"))
            and not is_low_value_arxiv_url(href)
            and (self._KEYWORDS.search(label) or self._KEYWORDS.search(href_signal))
        ):
            self.links.append((href, label))
        self._current_href, self._current_text = "", []


def compress_evidence(text: str, *, truncate_source_context: Callable[[str], str]) -> str:
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    keywords = re.compile(r"abstract|method|experiment|table|hardware|gpu|runtime|second|sec\b|dataset|benchmark|limitation|appendix|code|availability|status|supplement", re.I)
    selected = [line for line in lines if keywords.search(line)]
    merged = "\n".join((lines[:80] + selected)[:500])
    return truncate_source_context(merged)


def build_evidence_metadata(context: str, deep_scanned: bool) -> dict:
    text = context or ""

    def state(pattern: str) -> str:
        return "FOUND" if re.search(pattern, text, re.I) else ("SEARCHED_NOT_FOUND" if deep_scanned else "NOT_SEARCHED")

    qualifiers = []
    for match in re.finditer(r"(?:in|at least in) (simple|obvious)[^.\n]{0,100}(?:case|cases)|(?:単純な|明確に判定できる)[^。\n]{0,80}(?:例|ケース)", text, re.I):
        qualifiers.append(match.group(0).strip())
    metadata = {
        "coverage": {
            "method": state(r"\b(?:method|approach)\b|stage\s*[12]|方法"),
            "dataset": state(r"\b(?:dataset|data set)\b|データセット"),
            "hardware": state(r"\b(?:hardware|gpu|rtx|nvidia|cpu)\b|ハードウェア"),
            "runtime": state(r"\b(?:runtime|latency|sec|second|seconds)\b|処理時間"),
            "benchmark": state(r"benchmark|evaluation|experiment|評価"),
            "limitations": state(r"limitation|limitat|constraint|制約|限界"),
            "code_availability": state(r"source code|code availability|github|code release|公開コード"),
        },
        "required_qualifiers": list(dict.fromkeys(qualifiers))[:8],
        "evidence_strength": "OFFICIAL_GUARANTEE" if re.search(r"guarantee[sd]?|保証", text, re.I) else "UNKNOWN",
    }
    metadata["coverage"]["method"] = state(r"\b(?:method|approach|implementation|architecture|algorithm|api|package|function|interface)\b|stage\s*[12]|方法|実装|関数|パッケージ")
    metadata["coverage"]["benchmark"] = state(r"\b(?:benchmark|evaluation|experiment|test|release notes?)\b|評価|テスト|ベンチマーク")
    metadata["coverage"]["limitations"] = state(r"\b(?:limitation|limitations|constraint|constraints|WIP|experimental|unsupported)\b|work in progress|not supported|not implemented|does not support|制約|限界")
    metadata["named_technical_entities"] = list(dict.fromkeys(re.findall(
        r"(?<![A-Za-z0-9_])(?:[A-Z][A-Za-z0-9_]{2,}|[a-z][A-Za-z0-9_]*[A-Z][A-Za-z0-9_]*)\b", text
    )))[:80]
    metadata["numeric_claims"] = list(dict.fromkeys(re.findall(
        r"\b\d+(?:\.\d+)?(?:\s*(?:[-–—〜～]|to)\s*\d+(?:\.\d+)?)?\s*"
        r"(?:%|percent|ms|s|sec(?:onds?)?|minutes?|hours?|days?|weeks?|months?|KB|MB|GB|TB|x|倍|時間|分|日|週|ヶ月|か月)\b",
        text, re.I
    )))[:120]
    return metadata
