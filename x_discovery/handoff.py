from __future__ import annotations

from typing import Any, Dict, Sequence

from .models import DiscoveryCandidate
from .url_resolution import is_internal_x_url, is_unresolved_short_url


def build_primary_resolution_queue(candidates: Sequence[DiscoveryCandidate]) -> Dict[str, Any]:
    """Build an inert queue for later Factory-side primary-source verification.

    This is deliberately not a Factory write and never promotes evidence. Only URLs that
    already passed the conservative primary-domain candidate classifier are emitted.
    """
    items = []
    for candidate in candidates:
        url = candidate.canonical_url
        if not candidate.primary_source_candidate:
            continue
        if is_internal_x_url(url) or is_unresolved_short_url(url):
            continue
        items.append(
            {
                "canonical_url": url,
                "mention_count": int(candidate.mention_count),
                "authors": list(candidate.authors),
                "x_post_ids": list(candidate.post_ids),
                "x_post_urls": list(candidate.post_urls),
                "source_platform": "x",
                "source_role": "discovery_signal",
                "resolution_status": "candidate_needs_primary_verification",
                "evidence_status": "discovery_only",
                "is_evidence": False,
                "factory_write": False,
            }
        )

    items.sort(key=lambda item: (-item["mention_count"], item["canonical_url"]))
    return {
        "schema_version": 1,
        "queue_type": "x_primary_source_resolution",
        "source_platform": "x",
        "evidence_status": "discovery_only",
        "factory_write": False,
        "evidence_promoted": False,
        "item_count": len(items),
        "items": items,
    }
