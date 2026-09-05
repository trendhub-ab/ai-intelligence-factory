from __future__ import annotations

from pathlib import Path

README = Path("README.md")
SPEC = Path("AI_Intelligence_Factory_最終仕様書.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Run244 docs fail-closed: {label} count={count}")
    return text.replace(old, new, 1)


def reconcile_readme(text: str) -> str:
    text = replace_once(
        text,
        "- **Current pipeline modularization baseline:** Run243 — deterministic content-generation protocol extraction layered on prior modularized domains",
        "- **Current pipeline modularization baseline:** Run244 — deterministic Evidence sufficiency + Decision prompt + Product Review protocol extraction layered on prior modularized domains",
        "README baseline",
    )
    old = "- `content_generation_protocol.py` — canonical stdlib-only Fact Discipline / Human Editorial prompt rules, Gemini response parsing, conservative heading promotion and monthly Digest Markdown shaping; model invocation, quality-gate execution and persistence remain pipeline-owned"
    new = old + "\n- `evidence_sufficiency.py` — canonical deterministic Evidence-to-Decision sufficiency classification; live evidence URL normalization and existing sufficiency-state constants remain pipeline-bound\n- `product_review_protocol.py` — canonical provider-free Product Review prompt/schema/parser and Technology-state rehydration; model calls, candidate lookup, network acquisition and persistence remain pipeline-owned"
    text = replace_once(text, old, new, "README runtime map")
    return text


def reconcile_spec(text: str) -> str:
    text = replace_once(
        text,
        "Pipeline Modularization Baseline: **Run243 — deterministic content-generation protocol extraction layered on prior zero-quality-change strangler modularization**",
        "Pipeline Modularization Baseline: **Run244 — deterministic Evidence sufficiency + Decision prompt + Product Review protocol extraction layered on prior zero-quality-change strangler modularization**",
        "SPEC baseline",
    )
    run243 = "- Run243ではSource別Fact Discipline、Human Editorial / Reader Experience規律、Gemini応答parser、保守的なplain-text見出し昇格、月次Digest Markdown整形を`content_generation_protocol.py`へ抽出する。`generate_intelligence_report()`、Gemini呼出、品質Gate実行、Notion永続化は`pipeline.py`側に残し、11,172行から10,840行へ332行削減する。parserとDigest builderはlive callback/定数をkeyword注入する薄いwrapperで既存runtime bindingを維持する。"
    run244 = "- Run244ではEvidence-to-Decision sufficiencyを`evidence_sufficiency.py`へ、`build_decision_prompt()`を`content_generation_protocol.py`へ、Product Reviewのprompt/schema/parser/Technology-state rehydrateを`product_review_protocol.py`へ抽出する。Gemini/model呼出、`_call_product_review_pool()`、Product Review候補query、`run_product_reviews()`、source network/SSRF、Notion永続化、全Hard Gate実行は`pipeline.py`側に残し、10,840行から10,434行へ406行削減する。live定数/callbackは薄いwrapperから注入する。"
    text = replace_once(text, run243, run243 + "\n" + run244, "SPEC Run244 bullet")
    text = replace_once(
        text,
        "- Run235/236/237/238/239/240/241/242/243はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
        "- Run235/236/237/238/239/240/241/242/243/244はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
        "SPEC protected runs",
    )
    text = replace_once(
        text,
        "- Run243詳細: `docs/reference/RUN243_CONTENT_GENERATION_PROTOCOL_MODULARIZATION.md`",
        "- Run243詳細: `docs/reference/RUN243_CONTENT_GENERATION_PROTOCOL_MODULARIZATION.md`\n- Run244詳細: `docs/reference/RUN244_DECISION_PRODUCT_PROTOCOL_MODULARIZATION.md`",
        "SPEC Run244 ref",
    )
    return text


def main() -> None:
    readme = README.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")
    new_readme = reconcile_readme(readme)
    new_spec = reconcile_spec(spec)
    README.write_text(new_readme, encoding="utf-8")
    SPEC.write_text(new_spec, encoding="utf-8")
    print("RUN244_DOCUMENTATION_RECONCILIATION=PASS")


if __name__ == "__main__":
    main()
