"""Deterministic evidence-source authority classification.

Run118 separates *where an item was discovered* from *what may support a paid
Decision Intelligence assessment*.  The classifier is deliberately local and
zero-Gemini: it uses source channel, URL host/path, explicit labels/origins and
existing evidence roles.  It never promotes secondary/discovery material to
primary authority merely because it was successfully fetched.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

SOURCE_TYPES = {
    "GITHUB", "ARXIV", "OFFICIAL_DOCS", "OFFICIAL_BLOG", "OFFICIAL_CHANGELOG",
    "OFFICIAL_SITE", "AUTHOR_ORIGINAL", "INTERVIEW_PRIMARY", "REGULATORY",
    "SECONDARY_NEWS", "DISCOVERY", "OTHER_PRIMARY", "SUPPLEMENTAL", "UNKNOWN",
}
AUTHORITY_CLASSES = {
    "PRIMARY_FIRST_PARTY", "PRIMARY_REGULATORY", "PRIMARY_AUTHOR",
    "PRIMARY_INTERVIEW", "PRIMARY_OTHER", "SECONDARY", "DISCOVERY", "UNKNOWN",
}

DISCOVERY_HOST_SUFFIXES = ("news.ycombinator.com", "producthunt.com")
SECONDARY_NEWS_HOST_SUFFIXES = (
    "reuters.com", "apnews.com", "bloomberg.com", "techcrunch.com", "theverge.com",
    "wired.com", "arstechnica.com", "zdnet.com", "venturebeat.com", "cnbc.com",
    "engadget.com", "axios.com", "forbes.com", "fortune.com", "businessinsider.com",
)
REGULATORY_HOST_SUFFIXES = (
    "sec.gov", "ftc.gov", "nist.gov", "cisa.gov", "fda.gov", "justice.gov",
    "europa.eu", "ec.europa.eu", "edpb.europa.eu", "ico.org.uk",
)


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.")


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def _same_site(a: str, b: str) -> bool:
    ah, bh = _host(a), _host(b)
    return bool(ah and bh and (ah == bh or ah.endswith("." + bh) or bh.endswith("." + ah)))


def classify_evidence(
    *, url: str, role: str = "", raw_source_type: str = "", label: str = "",
    origin: str = "", pipeline_source: str = "", primary_url: str = "",
) -> dict:
    """Return a conservative authority classification for one evidence document.

    `decision_eligible` means the document may contribute to Decision Intelligence
    evidence authority.  It does not by itself make the overall assessment valid;
    all existing evidence/fact/relationship gates still apply.
    """
    host = _host(url)
    path = (urlparse(url or "").path or "").lower()
    role_u = str(role or "").upper()
    raw = str(raw_source_type or "").lower()
    label_l = str(label or "").lower()
    origin_l = str(origin or "").lower()
    source = str(pipeline_source or "")

    if not host:
        return {"source_type": "UNKNOWN", "authority_class": "UNKNOWN", "decision_eligible": False,
                "reason": "invalid or missing evidence URL"}

    if _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return {"source_type": "DISCOVERY", "authority_class": "DISCOVERY", "decision_eligible": False,
                "reason": "discovery platform is not decision authority"}

    if _host_matches(host, SECONDARY_NEWS_HOST_SUFFIXES):
        return {"source_type": "SECONDARY_NEWS", "authority_class": "SECONDARY", "decision_eligible": False,
                "reason": "secondary news may corroborate but cannot raise primary evidence authority"}

    if _host_matches(host, REGULATORY_HOST_SUFFIXES):
        return {"source_type": "REGULATORY", "authority_class": "PRIMARY_REGULATORY", "decision_eligible": True,
                "reason": "regulatory/government first-party source"}

    if host == "github.com" or host.endswith(".github.com"):
        return {"source_type": "GITHUB", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": role_u == "PRIMARY_SOURCE",
                "reason": "GitHub repository evidence"}

    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        return {"source_type": "ARXIV", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": role_u == "PRIMARY_SOURCE",
                "reason": "arXiv paper/version evidence"}

    # Explicit semantic signals from source discovery are stronger than guessing from domain alone.
    if re.search(r"changelog|release\s*notes?|what'?s\s+new", label_l + " " + path):
        return {"source_type": "OFFICIAL_CHANGELOG", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": role_u == "PRIMARY_SOURCE",
                "reason": "explicit changelog/release evidence"}
    if re.search(r"\bdocs?\b|documentation|reference|manual|guide", label_l + " " + path) or raw in {"official_docs", "boundary_official_docs"}:
        return {"source_type": "OFFICIAL_DOCS", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": role_u == "PRIMARY_SOURCE",
                "reason": "official documentation evidence"}
    if re.search(r"interview|q&a|qanda", label_l) and role_u == "PRIMARY_SOURCE":
        return {"source_type": "INTERVIEW_PRIMARY", "authority_class": "PRIMARY_INTERVIEW", "decision_eligible": True,
                "reason": "explicit primary interview evidence"}
    if re.search(r"blog|announcement|newsroom|press", label_l + " " + path) and (origin_l in {"metadata", "github_metadata", "landing", "boundary"} or _same_site(url, primary_url)):
        return {"source_type": "OFFICIAL_BLOG", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": role_u == "PRIMARY_SOURCE",
                "reason": "official blog/announcement evidence"}

    # Product Hunt official landing and GitHub repository homepage are explicit official-site signals.
    if origin_l in {"github_metadata", "metadata"} and role_u == "PRIMARY_SOURCE":
        return {"source_type": "OFFICIAL_SITE", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": True,
                "reason": "explicit official site from source metadata"}
    if source == "ProductHunt" and role_u == "PRIMARY_SOURCE" and not _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return {"source_type": "OFFICIAL_SITE", "authority_class": "PRIMARY_FIRST_PARTY", "decision_eligible": True,
                "reason": "Product Hunt discovery resolved to external primary site"}

    # Existing HN semantics allow an external author-original post to be primary, but known news hosts above never qualify.
    if source == "HackerNews" and role_u == "PRIMARY_SOURCE" and not _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return {"source_type": "AUTHOR_ORIGINAL", "authority_class": "PRIMARY_AUTHOR", "decision_eligible": True,
                "reason": "HN external primary/author-original source"}

    if role_u == "PRIMARY_SOURCE":
        # Preserve backward-compatible primary evidence without falsely calling it first-party.
        return {"source_type": "OTHER_PRIMARY", "authority_class": "PRIMARY_OTHER", "decision_eligible": True,
                "reason": "primary role retained; authority type not specifically identified"}
    if role_u == "SUPPLEMENTAL_SOURCE":
        return {"source_type": "SUPPLEMENTAL", "authority_class": "SECONDARY", "decision_eligible": False,
                "reason": "supplemental evidence cannot independently establish primary authority"}
    return {"source_type": "UNKNOWN", "authority_class": "UNKNOWN", "decision_eligible": False,
            "reason": "no explicit primary authority signal"}


def authority_rank(authority_class: str) -> int:
    return {
        "PRIMARY_REGULATORY": 4,
        "PRIMARY_FIRST_PARTY": 4,
        "PRIMARY_AUTHOR": 3,
        "PRIMARY_INTERVIEW": 3,
        "PRIMARY_OTHER": 2,
        "SECONDARY": 1,
        "DISCOVERY": 0,
        "UNKNOWN": 0,
    }.get(str(authority_class or "").upper(), 0)
