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


def _github_repo(url: str) -> str:
    if _host(url) != "github.com":
        return ""
    parts=[p for p in (urlparse(url or "").path or "").split("/") if p]
    return "/".join(parts[:2]).lower() if len(parts)>=2 else ""


def _arxiv_id(url: str) -> str:
    m=re.search(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?(?:$|[?#])", url or "", re.I)
    return m.group(1).lower() if m else ""


def _trusted_metadata_urls(details: dict | None) -> list[str]:
    details=details or {}; out=[]
    for key in ("official_url","officialUrl","website","website_url","homepage","project_url","docs_url","documentation_url","external_url"):
        v=details.get(key)
        if isinstance(v,str) and v.startswith(("http://","https://")): out.append(v)
    return out


def _entity_binding(*, url: str, entity_id: str, pipeline_source: str, primary_url: str, origin: str, source_details: dict | None, evidence_extract: str) -> tuple[str,str]:
    eid=(entity_id or "").lower().strip(); source=str(pipeline_source or ""); origin_l=str(origin or "").lower()
    if not eid:
        if _github_repo(url): return "IDENTITY_ANCHOR", "GitHub repository self-identifies when entity id is unavailable"
        if _arxiv_id(url): return "IDENTITY_ANCHOR", "arXiv paper self-identifies when entity id is unavailable"
        if primary_url and _same_site(url,primary_url) and not _host_matches(_host(primary_url), DISCOVERY_HOST_SUFFIXES + SECONDARY_NEWS_HOST_SUFFIXES):
            return "SAME_PRIMARY_SITE", "evidence matches resolved primary site when entity id is unavailable"
        if source in {"HackerNews","ProductHunt"} and not _host_matches(_host(url),DISCOVERY_HOST_SUFFIXES + SECONDARY_NEWS_HOST_SUFFIXES):
            return "LEGACY_RESOLVED_PRIMARY", "legacy resolved external primary without canonical entity id"
        if not _host_matches(_host(url),DISCOVERY_HOST_SUFFIXES + SECONDARY_NEWS_HOST_SUFFIXES):
            return "LEGACY_NO_ENTITY_CONTEXT", "legacy classifier call without canonical entity id; production must provide entity context"
        return "UNKNOWN", "canonical entity id unavailable"
    if eid.startswith("github:"):
        expected=eid.split(":",1)[1]
        if _github_repo(url)==expected:
            return "IDENTITY_ANCHOR", "exact GitHub owner/repository identity match"
        trusted=_trusted_metadata_urls(source_details)
        if any(_same_site(url,t) for t in trusted) and origin_l in {"github_metadata","metadata","boundary"}:
            return "OFFICIAL_METADATA", "same first-party site as explicit repository metadata"
        if any(_same_site(url,t) for t in trusted) and origin_l=="github_readme":
            return "OFFICIAL_METADATA", "README link matches explicit repository homepage/docs site"
        return "UNBOUND", "external evidence is not proven to belong to the GitHub entity"
    if eid.startswith("arxiv:"):
        expected=eid.split(":",1)[1].split("v",1)[0]
        if _arxiv_id(url)==expected:
            return "IDENTITY_ANCHOR", "exact arXiv paper identity match"
        return "UNBOUND", "external evidence is not the same arXiv paper identity"
    # For PH/HN/web entities, the resolved external primary site itself is the identity anchor.
    if primary_url and _same_site(url,primary_url) and not _host_matches(_host(primary_url), DISCOVERY_HOST_SUFFIXES + SECONDARY_NEWS_HOST_SUFFIXES):
        return "SAME_PRIMARY_SITE", "evidence is on the resolved entity primary site"
    # Regulatory evidence may bind a named web entity only when the extract contains a stable entity token.
    token=re.sub(r"[^a-z0-9]+"," ",eid.split(":",1)[-1]).strip()
    if _host_matches(_host(url),REGULATORY_HOST_SUFFIXES) and token and token in re.sub(r"[^a-z0-9]+"," ",(evidence_extract or "").lower()):
        return "CLAIM_BOUND", "regulatory evidence explicitly names the entity"
    return "UNKNOWN", "no deterministic entity-binding proof"


def classify_evidence(
    *, url: str, role: str = "", raw_source_type: str = "", label: str = "",
    origin: str = "", pipeline_source: str = "", primary_url: str = "",
    entity_id: str = "", source_details: dict | None = None, evidence_extract: str = "",
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
    binding,binding_reason=_entity_binding(url=url,entity_id=entity_id,pipeline_source=source,primary_url=primary_url,origin=origin,source_details=source_details,evidence_extract=evidence_extract)
    bound=binding not in {"UNBOUND","UNKNOWN"}

    def out(source_type, authority_class, eligible, reason):
        return {"source_type":source_type,"authority_class":authority_class,"decision_eligible":bool(eligible and bound),"reason":reason,"entity_binding":binding,"entity_binding_reason":binding_reason}
    if not host:
        return out("UNKNOWN","UNKNOWN",False,"invalid or missing evidence URL")

    if _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return out("DISCOVERY","DISCOVERY",False,"discovery platform is not decision authority")

    if _host_matches(host, SECONDARY_NEWS_HOST_SUFFIXES):
        return out("SECONDARY_NEWS","SECONDARY",False,"secondary news may corroborate but cannot raise primary evidence authority")

    if _host_matches(host, REGULATORY_HOST_SUFFIXES):
        return out("REGULATORY","PRIMARY_REGULATORY",True,"regulatory/government first-party source")

    if host == "github.com" or host.endswith(".github.com"):
        return out("GITHUB","PRIMARY_FIRST_PARTY",role_u == "PRIMARY_SOURCE","GitHub repository evidence")

    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        return out("ARXIV","PRIMARY_FIRST_PARTY",role_u == "PRIMARY_SOURCE","arXiv paper/version evidence")

    # Explicit semantic signals from source discovery are stronger than guessing from domain alone.
    if re.search(r"changelog|release\s*notes?|what'?s\s+new", label_l + " " + path):
        return out("OFFICIAL_CHANGELOG","PRIMARY_FIRST_PARTY",role_u == "PRIMARY_SOURCE","explicit changelog/release evidence")
    if re.search(r"\bdocs?\b|documentation|reference|manual|guide", label_l + " " + path) or raw in {"official_docs", "boundary_official_docs"}:
        return out("OFFICIAL_DOCS","PRIMARY_FIRST_PARTY",role_u == "PRIMARY_SOURCE","official documentation evidence")
    if re.search(r"interview|q&a|qanda", label_l) and role_u == "PRIMARY_SOURCE":
        return out("INTERVIEW_PRIMARY","PRIMARY_INTERVIEW",True,"explicit primary interview evidence")
    if re.search(r"blog|announcement|newsroom|press", label_l + " " + path) and (origin_l in {"metadata", "github_metadata", "landing", "boundary"} or _same_site(url, primary_url)):
        return out("OFFICIAL_BLOG","PRIMARY_FIRST_PARTY",role_u == "PRIMARY_SOURCE","official blog/announcement evidence")

    # Product Hunt official landing and GitHub repository homepage are explicit official-site signals.
    if origin_l in {"github_metadata", "metadata"} and role_u == "PRIMARY_SOURCE":
        return out("OFFICIAL_SITE","PRIMARY_FIRST_PARTY",True,"explicit official site from source metadata")
    if source == "ProductHunt" and role_u == "PRIMARY_SOURCE" and not _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return out("OFFICIAL_SITE","PRIMARY_FIRST_PARTY",True,"Product Hunt discovery resolved to external primary site")

    # Existing HN semantics allow an external author-original post to be primary, but known news hosts above never qualify.
    if source == "HackerNews" and role_u == "PRIMARY_SOURCE" and not _host_matches(host, DISCOVERY_HOST_SUFFIXES):
        return out("AUTHOR_ORIGINAL","PRIMARY_AUTHOR",True,"HN external primary/author-original source")

    if role_u == "PRIMARY_SOURCE":
        # Preserve backward-compatible primary evidence without falsely calling it first-party.
        return out("OTHER_PRIMARY","PRIMARY_OTHER",True,"primary role retained; authority type not specifically identified")
    if role_u == "SUPPLEMENTAL_SOURCE":
        return out("SUPPLEMENTAL","SECONDARY",False,"supplemental evidence cannot independently establish primary authority")
    return out("UNKNOWN","UNKNOWN",False,"no explicit primary authority signal")


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
