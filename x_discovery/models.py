from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DiscoverySignal:
    source_platform: str
    post_id: str
    author_handle: str
    post_url: str
    posted_at: Optional[str]
    text: str
    external_urls: List[str]
    engagement_snapshot: Dict[str, int]
    discovered_at: str
    provider: str
    evidence_status: str = "discovery_only"
    is_evidence: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryCandidate:
    canonical_url: str
    mention_count: int = 0
    authors: List[str] = field(default_factory=list)
    post_ids: List[str] = field(default_factory=list)
    post_urls: List[str] = field(default_factory=list)
    primary_source_candidate: bool = False
    source_platform: str = "x"
    evidence_status: str = "discovery_only"
    is_evidence: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
