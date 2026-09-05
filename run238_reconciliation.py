#!/usr/bin/env python3
"""One-shot fail-closed CI/documentation reconciliation for Run238."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
INTEGRATION = ROOT / ".github/workflows/integration-reconciliation-ci.yml"
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
README = ROOT / "README.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one old marker, found {count}")
    return text.replace(old, new, 1)


def reconcile_integration(text: str) -> str:
    text = replace_once(
        text,
        "# Run237: protected zero-api-regression owns modularization and Cross DB PR contract coverage.",
        "# Run238: protected zero-api-regression owns modularization and Cross DB PR contract coverage.",
        "integration header",
    )
    text = replace_once(
        text,
        "      - 'product_delivery_maintenance.py'\n      - 'legacy_eyecatch_renderer.py'",
        "      - 'product_delivery_maintenance.py'\n      - 'deep_dive_portfolio.py'\n      - 'legacy_eyecatch_renderer.py'",
        "integration path trigger",
    )
    text = replace_once(
        text,
        "            product_delivery_maintenance.py \\\n            run235_stage3b_source_normalization_migration.py \\",
        "            product_delivery_maintenance.py \\\n            deep_dive_portfolio.py \\\n            run235_stage3b_source_normalization_migration.py \\",
        "integration compile module",
    )
    text = replace_once(
        text,
        "            run237_product_delivery_maintenance_migration.py \\\n            legacy_eyecatch_renderer.py \\",
        "            run237_product_delivery_maintenance_migration.py \\\n            run238_deep_dive_portfolio_migration.py \\\n            legacy_eyecatch_renderer.py \\",
        "integration compile migration",
    )
    text = replace_once(
        text,
        "          python -m unittest tests.test_run237_product_delivery_maintenance_integration -v\n          python -m unittest tests.test_multilingual_title_normalization -v",
        "          python -m unittest tests.test_run237_product_delivery_maintenance_integration -v\n          python -m unittest tests.test_run238_deep_dive_portfolio_module -v\n          python -m unittest tests.test_run238_deep_dive_portfolio_integration -v\n          python -m unittest tests.test_multilingual_title_normalization -v",
        "integration modularization tests",
    )
    text = replace_once(
        text,
        "            product_delivery_maintenance.py\n          retention-days: 1",
        "            product_delivery_maintenance.py\n            deep_dive_portfolio.py\n          retention-days: 1",
        "integration artifact",
    )
    return text


def reconcile_spec(text: str) -> str:
    text = replace_once(
        text,
        "Pipeline Modularization Baseline: **Run237 — source-normalization + evidence-context + paid-product maintenance extraction / zero-quality-change strangler modularization**",
        "Pipeline Modularization Baseline: **Run238 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio extraction / zero-quality-change strangler modularization**",
        "spec baseline",
    )
    text = replace_once(
        text,
        "- Run237でEvidence Health、Subscriber Technology DB sync、月次Digest期間選択/生成の運用保守ロジックを`product_delivery_maintenance.py`へ抽出する。`pipeline.py`はlive runtime依存を渡す薄いwrapperだけを残し、Evidence Healthのzero-model契約と直近3完了月のDigest再確認順序を維持する。\n- Run235/236/237はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`",
        "- Run237でEvidence Health、Subscriber Technology DB sync、月次Digest期間選択/生成の運用保守ロジックを`product_delivery_maintenance.py`へ抽出する。`pipeline.py`はlive runtime依存を渡す薄いwrapperだけを残し、Evidence Healthのzero-model契約と直近3完了月のDigest再確認順序を維持する。\n- Run238でStock済みDeep Dive候補のprofit/portfolio並べ替え、topic diversity、EVERGREEN補助、publication reliability slotのzero-model決定論ロジックを`deep_dive_portfolio.py`へ抽出する。`pipeline.py`はlive閾値・normalizer・logger等を渡す薄いwrapperだけを残す。Eligibility、Decision/Evidence/Fact条件、既存toleranceは変更しない。\n- Run235/236/237/238はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`\n- Run238詳細: `docs/reference/RUN238_DEEP_DIVE_PORTFOLIO_MODULARIZATION.md`",
        "spec modularization bullets",
    )
    return text


def reconcile_readme(text: str) -> str:
    text = replace_once(
        text,
        "- **Current pipeline modularization baseline:** Run237 — source normalization, evidence context and paid-product maintenance ownership extraction",
        "- **Current pipeline modularization baseline:** Run238 — source normalization, evidence context, paid-product maintenance and Deep Dive portfolio ownership extraction",
        "README baseline",
    )
    text = replace_once(
        text,
        "- `product_delivery_maintenance.py` — canonical Evidence Health / subscriber sync / monthly Digest maintenance orchestration extracted from `pipeline.py`\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "- `product_delivery_maintenance.py` — canonical Evidence Health / subscriber sync / monthly Digest maintenance orchestration extracted from `pipeline.py`\n- `deep_dive_portfolio.py` — canonical zero-model Stock eligibility ordering, topic diversity, EVERGREEN and publication-reliability portfolio shaping extracted from `pipeline.py`\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer",
        "README runtime map",
    )
    return text


def main() -> int:
    integration_before = INTEGRATION.read_text(encoding="utf-8")
    spec_before = SPEC.read_text(encoding="utf-8")
    readme_before = README.read_text(encoding="utf-8")

    integration_after = reconcile_integration(integration_before)
    spec_after = reconcile_spec(spec_before)
    readme_after = reconcile_readme(readme_before)

    INTEGRATION.write_text(integration_after, encoding="utf-8")
    SPEC.write_text(spec_after, encoding="utf-8")
    README.write_text(readme_after, encoding="utf-8")

    print(
        "Run238 reconciliation: "
        f"integration_changed={integration_after != integration_before} "
        f"spec_changed={spec_after != spec_before} "
        f"readme_changed={readme_after != readme_before}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
