from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .models import DiscoveryCandidate, DiscoverySignal
from .url_resolution import is_primary_source_candidate


def load_seen_ids(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("post_ids", [])
    if not isinstance(payload, list):
        raise ValueError("seen id file must be a list or {'post_ids': [...]} object")
    return {str(item) for item in payload}


def save_seen_ids(path: Path, post_ids: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"post_ids": sorted({str(item) for item in post_ids})}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dedupe_signals(
    signals: Sequence[DiscoverySignal],
    seen_ids: Set[str],
) -> Tuple[List[DiscoverySignal], int, Set[str]]:
    emitted: List[DiscoverySignal] = []
    known = set(seen_ids)
    duplicates = 0
    for signal in signals:
        if signal.post_id in known:
            duplicates += 1
            continue
        known.add(signal.post_id)
        emitted.append(signal)
    return emitted, duplicates, known


def cluster_candidates(signals: Sequence[DiscoverySignal]) -> List[DiscoveryCandidate]:
    by_url: Dict[str, DiscoveryCandidate] = {}
    for signal in signals:
        for url in signal.external_urls:
            candidate = by_url.get(url)
            if candidate is None:
                candidate = DiscoveryCandidate(
                    canonical_url=url,
                    primary_source_candidate=is_primary_source_candidate(url),
                )
                by_url[url] = candidate
            candidate.mention_count += 1
            if signal.author_handle not in candidate.authors:
                candidate.authors.append(signal.author_handle)
            if signal.post_id not in candidate.post_ids:
                candidate.post_ids.append(signal.post_id)
            if signal.post_url and signal.post_url not in candidate.post_urls:
                candidate.post_urls.append(signal.post_url)
    return sorted(
        by_url.values(),
        key=lambda item: (-item.mention_count, item.canonical_url),
    )
