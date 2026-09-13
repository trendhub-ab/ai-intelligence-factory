"""Run386: zero-API triage for the 38 historical Ready rows from Run367.

This module does not call Gemini, Notion, GitHub APIs, or mutate publication state.
It parses the checked-in Run367 audit and classifies every row into the next safest
recovery action under the current Reader Repair contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

AUDIT_PATH = Path("docs/RUN367_READONLY_AUDIT.md")

REPAIRABLE_READER_LABELS = frozenset(
    {
        "dense_report_cluster",
        "repetitive_insight",
        "multi_axis_reader_weakness",
        "non_engineer_access_failure",
        "final_surface_multi_axis_reader_weakness",
        "final_surface_non_engineer_access_failure",
        "final_surface_summary_jargon_cluster",
        "final_surface_summary_fragment",
    }
)

PRODUCTHUNT_MIGRATED_TITLES = frozenset(
    {
        "AIエージェントの「記憶」を中央集権化せよ：Memmy Agentの実用的判断",
        "Wispr Flow Notetaker：会議後の「コピペ作業」を根絶するMCP時代の議事録最適化戦略",
        "SaaS依存から解放されるか：音声AI開発における「Dograh」の現実的な評価と導入戦略",
        "AI検索で自社が「無視」されていないかを確認する技術：AI Search Consoleの導入判断",
        "仕様書とコードの乖離をどう防ぐか。ビジネスロジック統合エンジン「GoRules」の登場から考える。",
    }
)

RUN385_PROVEN_TITLE = "Agent Memory as a File Format"


@dataclass(frozen=True)
class AuditRow:
    title: str
    classification: str
    reason: str


@dataclass(frozen=True)
class TriageRow:
    title: str
    bucket: str
    rationale: str


def _table_rows(text: str) -> list[AuditRow]:
    rows: list[AuditRow] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "## 38件の内訳":
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("## "):
            break
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) != 3 or cells[0] in {"記事", "---"} or cells[0].startswith("---"):
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(AuditRow(*cells))
    return rows


def parse_audit(path: Path = AUDIT_PATH) -> list[AuditRow]:
    return _table_rows(path.read_text(encoding="utf-8"))


def reader_labels(reason: str) -> set[str]:
    return set(re.findall(r"reader_value_review:([a-z0-9_]+)", str(reason or "")))


def classify(row: AuditRow) -> TriageRow:
    if row.classification == "unsupported":
        if row.title in PRODUCTHUNT_MIGRATED_TITLES:
            return TriageRow(
                row.title,
                "official_source_migrated_full_gate_revalidation",
                "ProductHunt旧契約は解消済み。公式一次情報へ再接地した本文を現行全Gateで再証明する。",
            )
        return TriageRow(
            row.title,
            "source_reground_required",
            "旧ProductHunt依存。公式一次情報との同一性・Fact/Evidence再接地が必要。",
        )

    if row.classification == "surface_clean_but_unproven":
        return TriageRow(
            row.title,
            "full_gate_proof_required",
            "文章表面はcleanだが、Fact/Evidence/Publication/画像を含む全Gate証明が不足。",
        )

    if row.classification == "gate_failed":
        labels = reader_labels(row.reason)
        if labels and labels <= REPAIRABLE_READER_LABELS:
            return TriageRow(
                row.title,
                "reader_repair_candidate",
                "Run373/378のReader-only理由集合。Evidence SUFFICIENT + decision_scope_safeなら1回だけReader Repair候補。",
            )
        return TriageRow(
            row.title,
            "manual_or_fact_repair_required",
            "Reader-only repair可能集合だけでは説明できない失敗理由を含む。",
        )

    return TriageRow(row.title, "unclassified", f"unknown audit class: {row.classification}")


def triage(rows: Iterable[AuditRow]) -> list[TriageRow]:
    return [classify(row) for row in rows]


def summarize(rows: Iterable[TriageRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.bucket] = counts.get(row.bucket, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(rows: list[TriageRow]) -> str:
    counts = summarize(rows)
    out = ["# Run386 Zero-API Recovery Triage", "", "## Counts", ""]
    for bucket, count in counts.items():
        out.append(f"- `{bucket}`: {count}")
    out += ["", "## Rows", "", "|記事|次の安全な処理|理由|", "|---|---|---|"]
    for row in rows:
        title = row.title.replace("|", "\\|")
        rationale = row.rationale.replace("|", "\\|")
        out.append(f"|{title}|{row.bucket}|{rationale}|")
    return "\n".join(out) + "\n"


def main() -> int:
    audit_rows = parse_audit()
    if len(audit_rows) != 38:
        raise SystemExit(f"Run386 fail-closed: expected 38 audit rows, got {len(audit_rows)}")
    triaged = triage(audit_rows)
    counts = summarize(triaged)
    print(f"RUN386_COUNTS={counts}")
    for row in triaged:
        print(f"RUN386_ROW\t{row.bucket}\t{row.title}")
    Path("run386_recovery_triage.md").write_text(render_markdown(triaged), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
