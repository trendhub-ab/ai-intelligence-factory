"""Run388: zero-model preflight for the six non-Reader rows left by Run386.

This is deliberately fail-closed. It proves which prerequisites can be established
without a Writer/model call and refuses to call a row FULL_GATE_PROVEN merely because
its source migration or surface audit looks clean.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryTarget:
    title: str
    page_id: str
    kind: str
    source_migrated: bool
    primary_evidence_rechecked: bool
    deterministic_surface_proven: bool
    full_fact_evidence_gate_proven: bool = False
    eyecatch_quality_proven: bool = False


TARGETS = (
    RecoveryTarget(
        "AIエージェントの「記憶」を中央集権化せよ：Memmy Agentの実用的判断",
        "3bc479ff-dca9-8116-a7e1-d1d7e2274f7d", "official_source_migration", True, True, False,
    ),
    RecoveryTarget(
        "Wispr Flow Notetaker：会議後の「コピペ作業」を根絶するMCP時代の議事録最適化戦略",
        "3bc479ff-dca9-815a-a6d3-d08da120a7bb", "official_source_migration", True, True, False,
    ),
    RecoveryTarget(
        "SaaS依存から解放されるか：音声AI開発における「Dograh」の現実的な評価と導入戦略",
        "3bc479ff-dca9-8191-859c-c6ace77dcfdd", "official_source_migration", True, True, False,
    ),
    RecoveryTarget(
        "AI検索で自社が「無視」されていないかを確認する技術：AI Search Consoleの導入判断",
        "3bc479ff-dca9-81cb-905d-f6f5452c66e5", "official_source_migration", True, True, False,
    ),
    RecoveryTarget(
        "仕様書とコードの乖離をどう防ぐか。ビジネスロジック統合エンジン「GoRules」の登場から考える。",
        "3c4479ff-dca9-81b6-813b-cd544200f14a", "official_source_migration", True, True, False,
    ),
    RecoveryTarget(
        "LLMを待たずに分岐する。公式比較「4ミリ秒」のSemantic Routerとは。",
        "3cd479ff-dca9-8142-bb39-c248314b251c", "surface_clean_but_unproven", True, True, True,
    ),
)


def classify(target: RecoveryTarget) -> str:
    if not target.source_migrated or not target.primary_evidence_rechecked:
        return "SOURCE_OR_EVIDENCE_RECHECK_REQUIRED"
    if not target.deterministic_surface_proven:
        return "DETERMINISTIC_SURFACE_REVALIDATION_REQUIRED"
    if not target.full_fact_evidence_gate_proven:
        return "FULL_FACT_EVIDENCE_GATE_REQUIRED"
    if not target.eyecatch_quality_proven:
        return "EYECATCH_QUALITY_PROOF_REQUIRED"
    return "FULL_GATE_PROVEN"


def main() -> int:
    if len(TARGETS) != 6 or len({t.page_id for t in TARGETS}) != 6:
        raise SystemExit("Run388 fail-closed: exact six-target inventory drift")
    counts: dict[str, int] = {}
    for target in TARGETS:
        state = classify(target)
        counts[state] = counts.get(state, 0) + 1
        print(f"RUN388_ROW\t{state}\t{target.title}\t{target.page_id}")
    if any(classify(t) == "FULL_GATE_PROVEN" for t in TARGETS):
        raise SystemExit("Run388 fail-closed: no row may be promoted without explicit full-gate proof")
    print(f"RUN388_COUNTS={dict(sorted(counts.items()))}")
    print("RUN388_MODEL_CALLS=0")
    print("RUN388_NOTION_WRITES=0")
    print("RUN388_PUBLICATION_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
