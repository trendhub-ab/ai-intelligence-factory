"""Run387: rank Run386 Reader Repair candidates without any model/API call."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import run386_zero_api_recovery_triage as r386


@dataclass(frozen=True)
class RankedCandidate:
    title: str
    labels: tuple[str, ...]
    tier: str
    complexity: int


def rank_candidate(row: r386.AuditRow) -> RankedCandidate:
    labels = tuple(sorted(r386.reader_labels(row.reason)))
    complexity = len(labels)
    if "dense_report_cluster" in labels:
        complexity += 1
    if "repetitive_insight" in labels:
        complexity += 1
    tier = "A" if complexity <= 2 else ("B" if complexity <= 4 else "C")
    return RankedCandidate(row.title, labels, tier, complexity)


def build_queue(path: Path = r386.AUDIT_PATH) -> list[RankedCandidate]:
    rows = [
        row
        for row in r386.parse_audit(path)
        if r386.classify(row).bucket == "reader_repair_candidate"
    ]
    ranked = [rank_candidate(row) for row in rows]
    return sorted(ranked, key=lambda x: (x.complexity, x.title))


def summarize(queue: list[RankedCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in queue:
        counts[item.tier] = counts.get(item.tier, 0) + 1
    return counts


def main() -> int:
    queue = build_queue()
    if len(queue) != 32:
        raise SystemExit(f"Run387 fail-closed: expected 32 Reader Repair candidates, got {len(queue)}")
    print(f"RUN387_TIER_COUNTS={summarize(queue)}")
    for i, item in enumerate(queue, 1):
        labels = ",".join(item.labels)
        print(f"RUN387_QUEUE\t{i:02d}\t{item.tier}\t{item.complexity}\t{labels}\t{item.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
