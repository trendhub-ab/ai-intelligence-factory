from __future__ import annotations
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence, found {count}: {old[:90]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    rf = ".github/workflows/repository-falsification.yml"
    replace_once(
        rf,
        "product_review_protocol.py run235_stage3b_source_normalization_migration.py",
        "product_review_protocol.py fact_validation_signals.py source_boundary_validation.py run245_fact_validation_migration.py run235_stage3b_source_normalization_migration.py",
    )
    replace_once(
        rf,
        "          python -m unittest tests.test_run244_decision_product_protocol_module -v\n",
        "          python -m unittest tests.test_run244_decision_product_protocol_module -v\n          python -m unittest tests.test_run245_fact_validation_modules -v\n",
    )

    ci = ".github/workflows/integration-reconciliation-ci.yml"
    replace_once(
        ci,
        "# Run244: protected zero-api-regression owns decision/evidence/product protocol modularization and Cross DB PR contract coverage.",
        "# Run245: protected zero-api-regression owns deterministic fact/source-boundary modularization and Cross DB PR contract coverage.",
    )
    replace_once(
        ci,
        "      - 'product_review_protocol.py'\n",
        "      - 'product_review_protocol.py'\n      - 'fact_validation_signals.py'\n      - 'source_boundary_validation.py'\n",
    )
    replace_once(
        ci,
        "            product_review_protocol.py \\\n            run235_stage3b_source_normalization_migration.py \\\n",
        "            product_review_protocol.py \\\n            fact_validation_signals.py \\\n            source_boundary_validation.py \\\n            run245_fact_validation_migration.py \\\n            run235_stage3b_source_normalization_migration.py \\\n",
    )
    replace_once(
        ci,
        "          python -m unittest tests.test_run244_decision_product_protocol_integration -v\n",
        "          python -m unittest tests.test_run244_decision_product_protocol_integration -v\n          python -m unittest tests.test_run245_fact_validation_modules -v\n          python -m unittest tests.test_run245_fact_validation_integration -v\n",
    )
    replace_once(
        ci,
        "            product_review_protocol.py\n",
        "            product_review_protocol.py\n            fact_validation_signals.py\n            source_boundary_validation.py\n",
    )

    readme = "README.md"
    replace_once(
        readme,
        "- **Current pipeline modularization baseline:** Run244 — deterministic Evidence sufficiency + Decision prompt + Product Review protocol extraction layered on prior modularized domains",
        "- **Current pipeline modularization baseline:** Run245 — deterministic Fact/Evidence validation + source-boundary validation extraction layered on prior modularized domains",
    )
    replace_once(
        readme,
        "- `product_review_protocol.py` — canonical provider-free Product Review prompt/schema/parser and Technology-state rehydration; model calls, candidate lookup, network acquisition and persistence remain pipeline-owned\n",
        "- `product_review_protocol.py` — canonical provider-free Product Review prompt/schema/parser and Technology-state rehydration; model calls, candidate lookup, network acquisition and persistence remain pipeline-owned\n- `fact_validation_signals.py` — canonical deterministic numeric-condition, hype/negation, false-negative/competitor and entity-relation validation signals mechanically extracted from `pipeline.py`; live regex sets/helpers remain pipeline-bound\n- `source_boundary_validation.py` — canonical deterministic evidence-alias expansion and unsupported named-fact source-boundary validation; network acquisition/SSRF and boundary reconciliation remain pipeline-owned\n",
    )

    spec = "AI_Intelligence_Factory_最終仕様書.md"
    replace_once(
        spec,
        "Pipeline Modularization Baseline: **Run244 — deterministic Evidence sufficiency + Decision prompt + Product Review protocol extraction layered on prior zero-quality-change strangler modularization**",
        "Pipeline Modularization Baseline: **Run245 — deterministic Fact/Evidence validation + source-boundary validation extraction layered on prior zero-quality-change strangler modularization**",
    )
    run244 = "- Run244ではEvidence-to-Decision sufficiencyを`evidence_sufficiency.py`へ、`build_decision_prompt()`を`content_generation_protocol.py`へ、Product Reviewのprompt/schema/parser/Technology-state rehydrateを`product_review_protocol.py`へ抽出する。Gemini/model呼出、`_call_product_review_pool()`、Product Review候補query、`run_product_reviews()`、source network/SSRF、Notion永続化、全Hard Gate実行は`pipeline.py`側に残し、10,840行から10,434行へ406行削減する。live定数/callbackは薄いwrapperから注入する。\n"
    run245 = "- Run245では数値Claim/条件照合、hype否定判定、false-negative/competitor、entity relation等の決定論Fact/Evidence検証を`fact_validation_signals.py`へ、Evidence alias展開とunsupported named-fact Source Boundary検証を`source_boundary_validation.py`へ機械的に抽出する。Gemini/model呼出、HTTP/network/SSRF取得、Product Review source reconciliation、Notion永続化、`validate_fact_gate()`を含むHard Gate実行本体は`pipeline.py`に残し、10,434行から9,972行へ462行削減する。既存regex・判定条件・fail-closed semanticsは変更せず、live定数/helperはcanonical関数を上書きしない形で薄いwrapperから再束縛する。\n"
    replace_once(spec, run244, run244 + run245)
    replace_once(
        spec,
        "- Run235/236/237/238/239/240/241/242/243/244はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
        "- Run235/236/237/238/239/240/241/242/243/244/245はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
    )
    replace_once(
        spec,
        "- Run244詳細: `docs/reference/RUN244_DECISION_PRODUCT_PROTOCOL_MODULARIZATION.md`\n",
        "- Run244詳細: `docs/reference/RUN244_DECISION_PRODUCT_PROTOCOL_MODULARIZATION.md`\n- Run245詳細: `docs/reference/RUN245_FACT_VALIDATION_MODULARIZATION.md`\n",
    )

    print("RUN245_REPOSITORY_RECONCILIATION=PASS")


if __name__ == "__main__":
    main()
