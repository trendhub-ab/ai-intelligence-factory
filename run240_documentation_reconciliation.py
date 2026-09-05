from pathlib import Path

README = Path("README.md")
SPEC = Path("AI_Intelligence_Factory_最終仕様書.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    readme = README.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")

    if "Current pipeline modularization baseline:** Run240" not in readme:
        readme = replace_once(
            readme,
            "- **Current pipeline modularization baseline:** Run239 — source normalization, evidence context, paid-product maintenance, Deep Dive portfolio and reader-experience diagnostics ownership extraction",
            "- **Current pipeline modularization baseline:** Run240 — source normalization, evidence context, paid-product maintenance, Deep Dive portfolio, reader-experience and editorial-naturalness diagnostics ownership extraction",
            "README baseline",
        )
        anchor = "- `reader_experience_signals.py` — canonical zero-API reader accessibility, proximity, delight and information-budget diagnostics mechanically extracted from `pipeline.py`; the pipeline keeps only the live opening-excerpt binding\n"
        readme = replace_once(
            readme,
            anchor,
            anchor + "- `editorial_naturalness.py` — canonical zero-API AI-style, human-editorial depth and cross-article naturalness diagnostics extracted from `pipeline.py`; live display variants, peer memory and opening behavior remain pipeline-bound\n",
            "README runtime map",
        )

    if "Pipeline Modularization Baseline: **Run240" not in spec:
        spec = replace_once(
            spec,
            "Pipeline Modularization Baseline: **Run239 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio + reader-experience diagnostics extraction / zero-quality-change strangler modularization**",
            "Pipeline Modularization Baseline: **Run240 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio + reader-experience + editorial-naturalness diagnostics extraction / zero-quality-change strangler modularization**",
            "SPEC baseline",
        )
        run239 = "- Run239で390行の`_reader_experience_signals()` zero-API診断実装を`reader_experience_signals.py`へ機械的に抽出する。`pipeline.py`にはliveな`_article_opening_excerpt`を束縛する薄いwrapperだけを残す。既存の正規表現、閾値、status、Reader Delight / information budget判定は変更せず、`soft_only=True`を維持する。\n"
        spec = replace_once(
            spec,
            run239,
            run239 + "- Run240でAI-style composite、human-editorial depth、cross-article fingerprint等のzero-API編集自然さ診断を`editorial_naturalness.py`へ抽出する。`pipeline.py`にはliveな`ARTICLE_DISPLAY_VARIANTS`、peer memory、opening helperを渡す薄いwrapperだけを残し、既存regex・score・thresholdを変更しない。\n",
            "SPEC Run240 contract",
        )
        spec = replace_once(
            spec,
            "- Run235/236/237/238/239はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
            "- Run235/236/237/238/239/240はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
            "SPEC non-change list",
        )
        anchor = "- Run239詳細: `docs/reference/RUN239_READER_EXPERIENCE_DIAGNOSTICS_MODULARIZATION.md`\n"
        spec = replace_once(
            spec,
            anchor,
            anchor + "- Run240詳細: `docs/reference/RUN240_EDITORIAL_NATURALNESS_MODULARIZATION.md`\n",
            "SPEC reference",
        )

    README.write_text(readme, encoding="utf-8")
    SPEC.write_text(spec, encoding="utf-8")
    print("RUN240_DOCUMENTATION_RECONCILIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
