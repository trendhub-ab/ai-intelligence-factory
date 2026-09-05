#!/usr/bin/env python3
"""One-shot fail-closed documentation reconciliation for Run239."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
README = ROOT / "README.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one old marker, found {count}")
    return text.replace(old, new, 1)


def reconcile_spec(text: str) -> str:
    text = replace_once(
        text,
        "Pipeline Modularization Baseline: **Run238 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio extraction / zero-quality-change strangler modularization**",
        "Pipeline Modularization Baseline: **Run239 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio + reader-experience diagnostics extraction / zero-quality-change strangler modularization**",
        "spec baseline",
    )
    old = (
        "- Run238でStock済みDeep Dive候補のprofit/portfolio並べ替え、topic diversity、EVERGREEN補助、publication reliability slotのzero-model決定論ロジックを`deep_dive_portfolio.py`へ抽出する。`pipeline.py`はlive閾値・normalizer・logger等を渡す薄いwrapperだけを残す。Eligibility、Decision/Evidence/Fact条件、既存toleranceは変更しない。\n"
        "- Run235/236/237/238はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n"
        "- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`\n"
        "- Run238詳細: `docs/reference/RUN238_DEEP_DIVE_PORTFOLIO_MODULARIZATION.md`"
    )
    new = (
        "- Run238でStock済みDeep Dive候補のprofit/portfolio並べ替え、topic diversity、EVERGREEN補助、publication reliability slotのzero-model決定論ロジックを`deep_dive_portfolio.py`へ抽出する。`pipeline.py`はlive閾値・normalizer・logger等を渡す薄いwrapperだけを残す。Eligibility、Decision/Evidence/Fact条件、既存toleranceは変更しない。\n"
        "- Run239で390行の`_reader_experience_signals()` zero-API診断実装を`reader_experience_signals.py`へ機械的に抽出する。`pipeline.py`にはliveな`_article_opening_excerpt`を束縛する薄いwrapperだけを残す。既存の正規表現、閾値、status、Reader Delight / information budget判定は変更せず、`soft_only=True`を維持する。\n"
        "- Run235/236/237/238/239はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n"
        "- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`\n"
        "- Run238詳細: `docs/reference/RUN238_DEEP_DIVE_PORTFOLIO_MODULARIZATION.md`\n"
        "- Run239詳細: `docs/reference/RUN239_READER_EXPERIENCE_DIAGNOSTICS_MODULARIZATION.md`"
    )
    return replace_once(text, old, new, "spec Run239 bullets")


def reconcile_readme(text: str) -> str:
    text = replace_once(
        text,
        "- **Current pipeline modularization baseline:** Run238 — source normalization, evidence context, paid-product maintenance and Deep Dive portfolio ownership extraction",
        "- **Current pipeline modularization baseline:** Run239 — source normalization, evidence context, paid-product maintenance, Deep Dive portfolio and reader-experience diagnostics ownership extraction",
        "README baseline",
    )
    text = replace_once(
        text,
        "- `deep_dive_portfolio.py` — canonical zero-model Stock eligibility ordering, topic diversity, EVERGREEN and publication-reliability portfolio shaping extracted from `pipeline.py`\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "- `deep_dive_portfolio.py` — canonical zero-model Stock eligibility ordering, topic diversity, EVERGREEN and publication-reliability portfolio shaping extracted from `pipeline.py`\n- `reader_experience_signals.py` — canonical zero-API reader accessibility, proximity, delight and information-budget diagnostics mechanically extracted from `pipeline.py`; the pipeline keeps only the live opening-excerpt binding\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "README runtime map",
    )
    return text


def main() -> int:
    spec_before = SPEC.read_text(encoding="utf-8")
    readme_before = README.read_text(encoding="utf-8")
    spec_after = reconcile_spec(spec_before)
    readme_after = reconcile_readme(readme_before)
    SPEC.write_text(spec_after, encoding="utf-8")
    README.write_text(readme_after, encoding="utf-8")
    print(
        "Run239 docs reconciliation: "
        f"spec_changed={spec_after != spec_before} "
        f"readme_changed={readme_after != readme_before}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
