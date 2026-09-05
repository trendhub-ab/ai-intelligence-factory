from pathlib import Path

README = Path('README.md')
SPEC = Path('AI_Intelligence_Factory_最終仕様書.md')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


readme = README.read_text()
readme = replace_once(
    readme,
    '- **Current pipeline modularization baseline:** Run240 — source normalization, evidence context, paid-product maintenance, Deep Dive portfolio, reader-experience and editorial-naturalness diagnostics ownership extraction',
    '- **Current pipeline modularization baseline:** Run241 — batched extraction of candidate identity, note manuscript shaping, gate diagnostics, Screening protocol and Source ROI policy in addition to prior modularized domains',
    'README baseline',
)
readme = replace_once(
    readme,
    '- `editorial_naturalness.py` — canonical zero-API AI-style, human-editorial depth and cross-article naturalness diagnostics extracted from `pipeline.py`; live display variants, peer memory and opening behavior remain pipeline-bound\n- `production_pipeline.py` — stable production entrypoint and runtime-layer installer',
    '- `editorial_naturalness.py` — canonical zero-API AI-style, human-editorial depth and cross-article naturalness diagnostics extracted from `pipeline.py`; live display variants, peer memory and opening behavior remain pipeline-bound\n'
    '- `candidate_identity.py` — canonical deterministic URL/candidate identity normalization for conservative cross-source dedupe\n'
    '- `note_manuscript.py` — canonical deterministic Reader-First note manuscript, source/evidence presentation and subscription CTA/tracking shaping; runtime attribution settings remain pipeline-bound\n'
    '- `gate_reasoning.py` — canonical reason-code/severity/disposition and audit-record shaping for already-produced gate outcomes; it does not execute quality gates\n'
    '- `screening_protocol.py` — canonical zero-I/O Screening metadata protocol, prompt/parser, topic and commercial/shelf helpers; model invocation remains outside this module\n'
    '- `source_roi_policy.py` — canonical zero-model Source ROI smoothing, profile, allocation and run-metric shaping with provider-failure exclusion preserved\n'
    '- `production_pipeline.py` — stable production entrypoint and runtime-layer installer',
    'README runtime map',
)
README.write_text(readme)

spec = SPEC.read_text()
spec = replace_once(
    spec,
    'Pipeline Modularization Baseline: **Run240 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio + reader-experience + editorial-naturalness diagnostics extraction / zero-quality-change strangler modularization**',
    'Pipeline Modularization Baseline: **Run241 — batched candidate-identity + note-manuscript + gate-reasoning + Screening-protocol + Source-ROI extraction layered on prior zero-quality-change strangler modularization**',
    'SPEC baseline',
)
spec = replace_once(
    spec,
    '- Run240でAI-style composite、human-editorial depth、cross-article fingerprint等のzero-API編集自然さ診断を`editorial_naturalness.py`へ抽出する。`pipeline.py`にはliveな`ARTICLE_DISPLAY_VARIANTS`、peer memory、opening helperを渡す薄いwrapperだけを残し、既存regex・score・thresholdを変更しない。\n- Run235/236/237/238/239/240はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。',
    '- Run240でAI-style composite、human-editorial depth、cross-article fingerprint等のzero-API編集自然さ診断を`editorial_naturalness.py`へ抽出する。`pipeline.py`にはliveな`ARTICLE_DISPLAY_VARIANTS`、peer memory、opening helperを渡す薄いwrapperだけを残し、既存regex・score・thresholdを変更しない。\n'
    '- Run241では低リスクな5領域を一括で抽出し、`candidate_identity.py`、`note_manuscript.py`、`gate_reasoning.py`、`screening_protocol.py`、`source_roi_policy.py`を正本化する。Gate実行本体・Gemini実行本体・Notion書込本体・Quota/Pending Retryは移動対象に含めない。`pipeline.py`はlive設定・callbackを渡す薄いwrapperを保持し、12,461行から11,497行へ964行削減する。\n'
    '- Run235/236/237/238/239/240/241はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。',
    'SPEC Run241 contract',
)
spec = replace_once(
    spec,
    '- Run240詳細: `docs/reference/RUN240_EDITORIAL_NATURALNESS_MODULARIZATION.md`',
    '- Run240詳細: `docs/reference/RUN240_EDITORIAL_NATURALNESS_MODULARIZATION.md`\n- Run241詳細: `docs/reference/RUN241_BATCHED_PIPELINE_MODULARIZATION.md`',
    'SPEC reference',
)
SPEC.write_text(spec)
print('Run241 documentation reconciliation: PASS')
