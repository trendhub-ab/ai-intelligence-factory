from __future__ import annotations

import http.client
import re
from typing import Dict, Iterable, List, Mapping, MutableSet, Optional, Sequence, Set
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.IGNORECASE)
_TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "ref", "ref_src",
    "ncid", "ocid", "wt.mc_id",
}
_INTERNAL_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
_TCO_HOSTS = {"t.co", "www.t.co"}
_OFFICIAL_SHORTENER_HOSTS = {"msft.it", "www.msft.it", "aka.ms", "www.aka.ms", "nvda.ws", "www.nvda.ws"}
_SHORTENER_HOSTS = _TCO_HOSTS | _OFFICIAL_SHORTENER_HOSTS
_PRIMARY_SOURCE_SUFFIXES = (
    "github.com",
    "arxiv.org",
    "openai.com",
    "chatgpt.com",
    "anthropic.com",
    "deepmind.google",
    "ai.google.dev",
    "developers.googleblog.com",
    "huggingface.co",
    "microsoft.com",
    "meta.com",
    "mistral.ai",
    "nvidia.com",
    "langchain.com",
    "llamaindex.ai",
    "perplexity.ai",
    "replicate.com",
    "cohere.com",
    "together.ai",
    "groq.com",
    "cursor.com",
    "stability.ai",
    "stabilityai.com",
    "stableaudio.com",
    "x.ai",
)
_TRAILING_PUNCTUATION = ".,;:!?)]}>、。！？）」』】"


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_internal_x_url(url: str) -> bool:
    return _host(url) in _INTERNAL_X_HOSTS


def is_unresolved_short_url(url: str) -> bool:
    return _host(url) in _SHORTENER_HOSTS


def canonicalize_url(url: str) -> Optional[str]:
    raw = (url or "").strip().rstrip(_TRAILING_PUNCTUATION)
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None

    host = parts.hostname.lower()
    if parts.port:
        default = (parts.scheme.lower() == "https" and parts.port == 443) or (
            parts.scheme.lower() == "http" and parts.port == 80
        )
        netloc = host if default else f"{host}:{parts.port}"
    else:
        netloc = host

    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_KEYS:
            continue
        query_items.append((key, value))
    query_items.sort()

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query_items, doseq=True), ""))


def _structured_urls(record: Mapping[str, object]) -> Iterable[str]:
    containers = []
    entities = record.get("entities")
    if isinstance(entities, Mapping):
        containers.append(entities.get("urls"))
    containers.append(record.get("urls"))

    for container in containers:
        if not isinstance(container, list):
            continue
        for item in container:
            if isinstance(item, str):
                yield item
                continue
            if not isinstance(item, Mapping):
                continue
            for key in ("expanded_url", "expandedUrl", "unwound_url", "unwoundUrl", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    yield value
                    break


def extract_external_urls(record: Mapping[str, object], text: str) -> List[str]:
    seen: MutableSet[str] = set()
    result: List[str] = []
    raw_urls = list(_structured_urls(record)) + _URL_RE.findall(text or "")
    for raw in raw_urls:
        canonical = canonicalize_url(raw)
        if not canonical:
            continue
        if is_internal_x_url(canonical) or is_unresolved_short_url(canonical):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


class AllowlistedShortenerResolver:
    """Resolve redirect chains only while the connected host is explicitly allowlisted.

    Destination hosts are never fetched. A chain may continue only when the next hop is
    another allowlisted shortener. This lets msft.it -> aka.ms -> destination work without
    turning this component into an arbitrary URL fetcher.
    """

    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str],
        timeout_seconds: int = 8,
        max_hops: int = 1,
    ):
        hosts = {str(host).lower().strip() for host in allowed_hosts if str(host).strip()}
        if not hosts or not hosts.issubset(_SHORTENER_HOSTS):
            raise ValueError("resolver hosts must be a non-empty subset of known shorteners")
        if not 1 <= int(max_hops) <= 3:
            raise ValueError("max_hops must be between 1 and 3")
        self.allowed_hosts: Set[str] = hosts
        self.timeout_seconds = int(timeout_seconds)
        self.max_hops = int(max_hops)
        self.calls = 0
        self.network_requests = 0
        self.successes = 0
        self.internal_resolutions = 0
        self.unresolved_chains = 0
        self.failures = 0
        self.cache: Dict[str, Optional[str]] = {}

    def handles(self, url: str) -> bool:
        canonical = canonicalize_url(url)
        return bool(canonical and _host(canonical) in self.allowed_hosts)

    def _first_location(self, url: str) -> Optional[str]:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host not in self.allowed_hosts:
            return None
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        for method in ("HEAD", "GET"):
            conn = http.client.HTTPSConnection(host, timeout=self.timeout_seconds)
            self.network_requests += 1
            try:
                conn.request(
                    method,
                    path,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; ai-intelligence-factory-url-resolver/0.3)",
                        "Accept": "*/*",
                    },
                )
                response = conn.getresponse()
                location = response.getheader("Location")
                if method == "GET":
                    response.read(1)
                if location:
                    return urljoin(url, location)
            except Exception:
                pass
            finally:
                conn.close()
        return None

    def resolve(self, url: str) -> Optional[str]:
        canonical_short = canonicalize_url(url)
        if not canonical_short or _host(canonical_short) not in self.allowed_hosts:
            return None
        if canonical_short in self.cache:
            return self.cache[canonical_short]

        self.calls += 1
        current = canonical_short
        for hop in range(self.max_hops):
            location = self._first_location(current)
            resolved = canonicalize_url(location or "")
            if not resolved:
                self.failures += 1
                self.cache[canonical_short] = None
                return None

            if is_internal_x_url(resolved):
                self.internal_resolutions += 1
                self.cache[canonical_short] = None
                return None

            next_host = _host(resolved)
            if next_host in _SHORTENER_HOSTS:
                if next_host in self.allowed_hosts and hop + 1 < self.max_hops:
                    current = resolved
                    continue
                self.unresolved_chains += 1
                self.cache[canonical_short] = None
                return None

            self.successes += 1
            self.cache[canonical_short] = resolved
            return resolved

        self.unresolved_chains += 1
        self.cache[canonical_short] = None
        return None


class TcoRedirectResolver(AllowlistedShortenerResolver):
    """Start only from t.co, but safely continue through owned shorteners if chained."""

    def __init__(self, *, timeout_seconds: int = 8):
        super().__init__(
            allowed_hosts=tuple(_SHORTENER_HOSTS),
            timeout_seconds=timeout_seconds,
            max_hops=3,
        )

    def handles(self, url: str) -> bool:
        canonical = canonicalize_url(url)
        return bool(canonical and _host(canonical) in _TCO_HOSTS)

    def resolve(self, url: str) -> Optional[str]:
        canonical = canonicalize_url(url)
        if not canonical or _host(canonical) not in _TCO_HOSTS:
            return None
        return super().resolve(canonical)


class OfficialShortenerResolver(AllowlistedShortenerResolver):
    """Resolve Microsoft/NVIDIA-owned shorteners; never fetch the destination host."""

    def __init__(self, *, timeout_seconds: int = 8):
        super().__init__(
            allowed_hosts=tuple(_OFFICIAL_SHORTENER_HOSTS),
            timeout_seconds=timeout_seconds,
            max_hops=2,
        )


def _record_text(record: Mapping[str, object]) -> str:
    for key in ("text", "full_text", "fullText", "content"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def enrich_record_with_shorteners(
    record: Mapping[str, object],
    resolvers: Sequence[AllowlistedShortenerResolver],
) -> Dict[str, object]:
    enriched: Dict[str, object] = dict(record)
    text = _record_text(record)
    structured = list(_structured_urls(record))
    raw_urls = structured + _URL_RE.findall(text)

    output_urls: List[str] = []
    seen: Set[str] = set()
    for raw in raw_urls:
        canonical = canonicalize_url(raw)
        if not canonical:
            continue

        resolver = next((item for item in resolvers if item.handles(canonical)), None)
        if resolver is not None:
            resolved = resolver.resolve(canonical)
            if resolved and resolved not in seen:
                seen.add(resolved)
                output_urls.append(resolved)
            continue

        # Keep ordinary URLs and shorteners assigned to another resolver; downstream
        # extraction filters unresolved shorteners fail-closed.
        if canonical not in seen:
            seen.add(canonical)
            output_urls.append(canonical)

    if output_urls:
        enriched["urls"] = output_urls
    elif "urls" in enriched:
        enriched["urls"] = []
    return enriched


def enrich_record_with_tco(record: Mapping[str, object], resolver: TcoRedirectResolver) -> Dict[str, object]:
    return enrich_record_with_shorteners(record, [resolver])


def is_primary_source_candidate(url: str) -> bool:
    host = _host(url)
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in _PRIMARY_SOURCE_SUFFIXES)
