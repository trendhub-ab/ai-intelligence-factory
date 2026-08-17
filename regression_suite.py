#!/usr/bin/env python3
"""AI Intelligence Factory: synthetic/adversarial evidence regression suite.

This runner is intentionally offline by default. It never writes to Notion,
publishes, or calls a model. It uses the production module's credential-free
validation adapter against multi-document local fixtures and deterministic
Ground Truth, so its assertions cannot silently drift away from pipeline.py.
"""
from __future__ import annotations

import argparse, hashlib, json, os, random, re, shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SUITE_VERSION = "1.0.0"
PIPELINE_VERSION = os.environ.get("PIPELINE_VERSION", "pipeline.py")
TODAY = date.fromisoformat(os.environ.get("REGRESSION_CURRENT_DATE", "2026-08-16"))
CRITICAL = {"INV-002", "INV-004", "INV-007", "INV-014", "INV-015", "INV-017", "INV-019", "INV-020"}
SEVERITY = {"critical": 20, "major": 10, "moderate": 4, "minor": 1}

@dataclass
class Finding:
    code: str
    severity: str
    stage: str
    message: str

def _write(path: Path, value: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n" if isinstance(value, dict) else value, encoding="utf-8")

def _case_id(category: str, n: int) -> str:
    return f"{category}_{n:03d}"

def case_spec(category: str, n: int, kind: str, holdout: bool) -> dict:
    """Deterministic source + truth generator.  Facts vary without changing semantics."""
    samples = [5, 20, 100, 10000][n % 4]
    hardware = ["CPU", "RTX 3090", "RTX 4090", "H100"][n % 4]
    old = "planned" if n % 2 else "accepted"
    base = {
        "case_id": _case_id(category, n), "category": [category], "kind": kind,
        "generation_seed": n, "generator_version": SUITE_VERSION, "source_type": "research_paper",
        "facts": [], "allowed_claims": [], "forbidden_claims": [], "required_qualifiers": [],
        "numerical_truth": {}, "dataset_roles": {}, "temporal_truth": {}, "limitations": [],
        "expected_flags": [], "source_priority": {"landing_page": 1, "paper": 3, "supplemental": 4, "followup": 5},
    }
    docs = {"landing_page.md": "Project landing page\n", "paper.md": "", "supplemental.md": "", "followup.md": ""}
    if category == "scope":
        docs["paper.md"] = f"We evaluated 22 of 153 safeguards, limited to topology-visible safeguards.\n"
        base.update(facts=[{"id":"F1","claim":"22 safeguards evaluated","scope":"topology-visible subset","evidence_class":"CONTROLLED_EXPERIMENT"}], required_qualifiers=["22 safeguards", "topology-visible"], forbidden_claims=["CIS完全準拠", "CIS Controls v8.1.2準拠"], expected_flags=["INV-002"])
    elif category in {"numerical", "dataset_roles"}:
        docs["paper.md"] = "Reference retrieval set: 22 templates / 44 intents. Held-out evaluation set: 7 templates / 14 intents. Synthetic benchmark only.\n"
        base.update(numerical_truth={"reference_templates":22,"reference_intents":44,"held_out_templates":7,"held_out_intents":14}, dataset_roles={"reference":"retrieval","held_out":"evaluation","synthetic":"benchmark"}, required_qualifiers=["22", "7", "held-out", "synthetic"], forbidden_claims=["21 templates", "58 intents", "非公開テンプレート", "本番データ"], expected_flags=["INV-003","INV-016","INV-019","INV-020"])
    elif category == "claim_strength":
        docs["paper.md"] = "The preliminary result suggests the method may improve latency.\n"
        base.update(required_qualifiers=["予備的", "可能性"], forbidden_claims=["改善する", "証明した", "保証する"], expected_flags=["INV-008"])
    elif category == "toy_example":
        docs["paper.md"] = "In one toy program, the compiler emits a single lea instruction.\n"
        base.update(required_qualifiers=["単純な例", "原著の例"], forbidden_claims=["1命令になる", "ゼロコスト"], expected_flags=["INV-001"])
    elif category == "compliance":
        docs["paper.md"] = "Self-assessed alignment was checked for selected controls; this is not certification.\n"
        base.update(required_qualifiers=["自己評価", "選択された", "認証ではない"], forbidden_claims=["認証済み", "完全準拠"], expected_flags=["INV-002","INV-014"])
    elif category == "security":
        docs["paper.md"] = "The implementation does not require an executable stack and is compatible with NX stack.\n"
        base.update(required_qualifiers=["実行可能スタックを不要", "NX"], forbidden_claims=["完全に安全", "脆弱性を防止", "安全なクロージャ"], expected_flags=["INV-017"])
    elif category in {"actor_attribution", "research_status"}:
        docs["paper.md"] = "An individual developer proposed a patch. It was merged into the development branch, not a stable release.\n"
        base.update(required_qualifiers=["開発ブランチ", "個人開発者"], forbidden_claims=["正式標準", "安定版リリース", "プロジェクト全体の方針"], expected_flags=["INV-012","INV-018"])
    elif category in {"temporal_status", "freshness", "followup"}:
        docs["landing_page.md"] = f"2026-07-01: feature {old}.\n"
        docs["followup.md"] = "2026-08-01: official release notes: feature released.\n"
        base.update(temporal_truth={"current_status":"released","current_status_date":"2026-08-01"}, required_qualifiers=["リリース済み"], forbidden_claims=["リリース予定", "計画中"], expected_flags=["INV-007"])
    elif category in {"deep_extraction", "tables", "hardware_conditions", "benchmark_conditions", "supplemental", "limitations", "absence_claims"}:
        docs["landing_page.md"] = "Fast project.\n"
        docs["paper.md"] = f"Table 4 | hardware: {hardware} | 512px runtime: 6.37 sec | benchmark: synthetic | n={samples}.\n"
        docs["supplemental.md"] = "Limitation: the result has not been validated in production.\n"
        base.update(numerical_truth={"runtime_seconds":6.37,"sample_count":samples}, required_qualifiers=[hardware, "合成ベンチマーク", "本番未検証"], limitations=["not validated in production"], forbidden_claims=["一般PCで高速", "本番で実証", "hardwareは確認できない", "real-world performance"], expected_flags=["INV-004","INV-005","INV-009","INV-010","INV-011","INV-015"])
    elif category in {"author_opinion", "production_readiness"}:
        docs["paper.md"] = "This is a lab experiment only. The authors believe it may become a standard and could be useful in production.\n"
        base.update(required_qualifiers=["著者は", "可能性", "実験室"], forbidden_claims=["新標準になる", "すぐに導入", "production-ready"], expected_flags=["INV-008"])
    elif category == "code_availability":
        docs["paper.md"] = "Code is planned; the demonstration is available, but the repository is empty.\n"
        base.update(required_qualifiers=["コードは公開予定", "デモ"], forbidden_claims=["ソースコード公開済み"], expected_flags=["INV-013"])
    elif category in {"translation_semantics", "final_wording"}:
        docs["paper.md"] = "Held-out evaluation uses synthetic data. In simple cases only, a warning is emitted.\n"
        base.update(required_qualifiers=["held-out", "合成", "単純なケース"], forbidden_claims=["非公開データ", "常に警告"], expected_flags=["INV-003","INV-006","INV-016"])
    elif category in {"source_conflicts", "multi_source_priority"}:
        docs["landing_page.md"] = "2026-07-01 landing page: runtime 5 sec.\n"
        docs["paper.md"] = "2026-07-15 paper: runtime 6 sec under benchmark conditions.\n"
        docs["followup.md"] = "2026-08-01 official release note: runtime 4 sec in a new release configuration.\n"
        base.update(required_qualifiers=["条件が異なる", "4 sec"], forbidden_claims=["常に4秒", "5秒である"], expected_flags=["SOURCE_CONFLICT"])
    else:
        docs["paper.md"] = "Official specification guarantees protocol conformance under the stated conditions.\n"
        base.update(required_qualifiers=["仕様上", "条件下"], forbidden_claims=["かもしれない"], expected_flags=[])
    base["documents"] = docs
    return base

CATEGORIES = ["scope","numerical","dataset_roles","claim_strength","toy_example","compliance","security","actor_attribution","temporal_status","freshness","followup","deep_extraction","absence_claims","tables","supplemental","hardware_conditions","benchmark_conditions","limitations","author_opinion","research_status","code_availability","production_readiness","translation_semantics","source_conflicts","final_wording","multi_source_priority"]

def bootstrap(fixtures: Path) -> Counter:
    """Creates exactly 500 local, reviewable cases: 200 deterministic, 200 pairwise, 100 adversarial (100 hidden)."""
    if fixtures.exists(): shutil.rmtree(fixtures)
    counts = Counter()
    for i in range(500):
        kind = "deterministic" if i < 200 else "combinational" if i < 400 else "adversarial"
        cat = CATEGORIES[i % len(CATEGORIES)]
        holdout = i >= 400
        spec = case_spec(cat, i + 1, kind, holdout)
        # Pairwise cases retain two independent trap classes, adversarial include noise.
        if kind == "combinational":
            spec["category"].append(CATEGORIES[(i * 7 + 3) % len(CATEGORIES)])
        if kind == "adversarial":
            spec["documents"]["landing_page.md"] += "Historical comparison: 78% baseline, unrelated competitor: 88%.\n"
        folder = fixtures / ("holdout" if holdout else "visible") / spec["case_id"]
        _write(folder / "ground_truth.json", spec)
        for name, text in spec.pop("documents").items(): _write(folder / name, text)
        counts[kind] += 1
    _write(fixtures / "suite_manifest.json", {"suite_version":SUITE_VERSION, "seed":20260816, "counts":dict(counts), "holdout":100, "categories":CATEGORIES})
    return counts

def text_for_case(case_dir: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in case_dir.glob("*.md"))

def default_article(gt: dict) -> str:
    """Conservative reference adapter; replace by a model-produced article to audit full wording."""
    pieces = ["## Synthetic regression result"]
    q = gt.get("required_qualifiers", [])
    if q: pieces.append("一次情報の限定条件: " + "、".join(q) + "。")
    numeric = gt.get("numerical_truth", {})
    if numeric:
        pieces.append("構造化した数値: " + "、".join(f"{k}={v}" for k, v in numeric.items()) + "。")
    if gt.get("limitations"): pieces.append("制約: " + "、".join(gt["limitations"]) + "。")
    if gt.get("temporal_truth", {}).get("current_status"): pieces.append("現在の状態: リリース済み。")
    return "\n".join(pieces)

def audit_article(gt: dict, article: str, evidence: str) -> list[Finding]:
    # The suite is offline, but its assertions must be executed by the
    # production module rather than a detached copy of the validator.
    from pipeline import validate_synthetic_invariants
    return [Finding(**row) for row in validate_synthetic_invariants(gt, article, evidence)]

def run(fixtures: Path, tier: str, external_articles: Path | None = None) -> dict:
    selection = {"smoke":30,"core":150,"full":500}[tier]
    paths = sorted(fixtures.glob("**/ground_truth.json"))
    if tier != "full": paths = paths[:selection]
    rows, all_findings = [], []
    for p in paths:
        gt = json.loads(p.read_text(encoding="utf-8")); case_dir = p.parent
        article_path = external_articles / gt["case_id"] / "article.md" if external_articles else None
        article = article_path.read_text(encoding="utf-8") if article_path and article_path.exists() else default_article(gt)
        findings = audit_article(gt, article, text_for_case(case_dir))
        all_findings.extend(findings)
        rows.append({"case_id":gt["case_id"],"category":gt["category"],"kind":gt["kind"],"holdout":"holdout" in case_dir.parts,"passed":not findings,"findings":[asdict(x) for x in findings]})
    clusters = Counter(f.code for f in all_findings); critical = [f for f in all_findings if f.severity == "critical"]
    category = defaultdict(lambda:[0,0])
    for row in rows:
        for c in row["category"]: category[c][0] += 1; category[c][1] += int(row["passed"])
    return {"suite_version":SUITE_VERSION,"pipeline_version":PIPELINE_VERSION,"run_date":str(TODAY),"tier":tier,"model_configuration":"offline deterministic validator","production_write_isolation":True,"total_cases":len(rows),"passed":sum(r["passed"] for r in rows),"failed":sum(not r["passed"] for r in rows),"critical_failures":len(critical),"major_failures":sum(f.severity=="major" for f in all_findings),"critical_invariants_pass":not critical,"failure_clusters":dict(clusters),"category_pass_rates":{k:round(v[1]/v[0],4) for k,v in category.items()},"examples":[r for r in rows if not r["passed"]][:10],"cases":rows}

def report_md(report: dict) -> str:
    lines=[f"# Regression Suite {report['suite_version']} — {report['tier']}","",f"- Cases: {report['total_cases']}",f"- Passed: {report['passed']}",f"- Failed: {report['failed']}",f"- Critical failures: {report['critical_failures']}",f"- Production writes: disabled", "", "## Failure clusters", ""]
    lines += [f"- {k}: {v}" for k,v in sorted(report["failure_clusters"].items())] or ["- None"]
    return "\n".join(lines)+"\n"

def self_test() -> None:
    good={"required_qualifiers":["単純な例"],"forbidden_claims":["ゼロコスト"],"numerical_truth":{},"expected_flags":["INV-001"]}
    assert not audit_article(good,"原著の例では。","")
    assert audit_article(good,"ゼロコスト。","")
    assert audit_article({"required_qualifiers":[],"forbidden_claims":[],"numerical_truth":{},"expected_flags":[]},"hardwareは確認できない","Hardware: RTX 4090")

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--bootstrap",action="store_true"); ap.add_argument("--smoke",action="store_true"); ap.add_argument("--core",action="store_true"); ap.add_argument("--full",action="store_true"); ap.add_argument("--self-test",action="store_true"); ap.add_argument("--fixtures",default="regression_suite/fixtures"); ap.add_argument("--articles-dir"); ap.add_argument("--output-dir",default="regression_suite_runs")
    a=ap.parse_args(); fixtures=ROOT/a.fixtures
    if a.self_test: self_test(); print("harness self-test: PASS"); return
    if a.bootstrap or not fixtures.exists(): bootstrap(fixtures)
    tier="full" if a.full else "core" if a.core else "smoke"
    result=run(fixtures,tier,ROOT/a.articles_dir if a.articles_dir else None)
    run_id=f"{TODAY}_{tier}_{hashlib.sha1(json.dumps(result['cases'],sort_keys=True).encode()).hexdigest()[:8]}"; out=ROOT/a.output_dir/run_id
    _write(out/"regression_report.json",result); _write(out/"regression_summary.md",report_md(result)); print(out)
    raise SystemExit(1 if result["critical_failures"] else 0)
if __name__ == "__main__": main()
