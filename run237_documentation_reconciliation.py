#!/usr/bin/env python3
"""One-shot guarded reconciliation of canonical docs for Run237."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
README = ROOT / "README.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one old marker, found {count}")
    return text.replace(old, new, 1)


def reconcile_spec(text: str) -> str:
    text = replace_once(
        text,
        "Pipeline Modularization Baseline: **Run236 — source-normalization + pure evidence-context extraction / zero-quality-change strangler modularization**",
        "Pipeline Modularization Baseline: **Run237 — source-normalization + evidence-context + paid-product maintenance extraction / zero-quality-change strangler modularization**",
        "spec baseline",
    )
    text = replace_once(
        text,
        "- Run236でEvidence本文のtruncate/excerpt/mergeロジックをprovider・DB非依存の`evidence_context.py`へ抽出する。`pipeline.py`には現行の動的文字数上限を束縛する薄いwrapperだけを残す。\n- Run235/236はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
        "- Run236でEvidence本文のtruncate/excerpt/mergeロジックをprovider・DB非依存の`evidence_context.py`へ抽出する。`pipeline.py`には現行の動的文字数上限を束縛する薄いwrapperだけを残す。\n- Run237でEvidence Health、Subscriber Technology DB sync、月次Digest期間選択/生成の運用保守ロジックを`product_delivery_maintenance.py`へ抽出する。`pipeline.py`はlive runtime依存を渡す薄いwrapperだけを残し、Evidence Healthのzero-model契約と直近3完了月のDigest再確認順序を維持する。\n- Run235/236/237はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`",
        "spec modularization bullets",
    )
    return text


def reconcile_readme(text: str) -> str:
    text = replace_once(
        text,
        "- **Current free article reader rhythm baseline:** Run228 — evidence-preserving reader rhythm / dense-report prevention without style quotas\n- **Current repository organization baseline:** Run201 — repository garbage cleanup without intended runtime behavior change",
        "- **Current free article reader rhythm baseline:** Run228 — evidence-preserving reader rhythm / dense-report prevention without style quotas\n- **Current pipeline modularization baseline:** Run237 — source normalization, evidence context and paid-product maintenance ownership extraction\n- **Current repository organization baseline:** Run201 — repository garbage cleanup without intended runtime behavior change",
        "README baseline",
    )
    text = replace_once(
        text,
        "- `pipeline.py` — acquisition, screening, Deep Dive, article quality, Notion persistence and operational state\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "- `pipeline.py` — acquisition, screening, Deep Dive, article quality, Notion persistence and top-level orchestration; extracted domains remain compatibility wrappers only\n- `source_normalization.py` — canonical source/title/display normalization extracted from `pipeline.py`\n- `evidence_context.py` — canonical provider-free source/verification context shaping extracted from `pipeline.py`\n- `product_delivery_maintenance.py` — canonical Evidence Health / subscriber sync / monthly Digest maintenance orchestration extracted from `pipeline.py`\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "README runtime map",
    )
    return text


def main() -> int:
    spec_before = SPEC.read_text(encoding="utf-8")
    readme_before = README.read_text(encoding="utf-8")
    spec_after = reconcile_spec(spec_before)
    readme_after = reconcile_readme(readme_before)
    if spec_after != spec_before:
        SPEC.write_text(spec_after, encoding="utf-8")
    if readme_after != readme_before:
        README.write_text(readme_after, encoding="utf-8")
    print(
        "Run237 documentation reconciliation: "
        f"spec_changed={spec_after != spec_before} readme_changed={readme_after != readme_before}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
