from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1))


readme = Path("README.md")
replace_once(
    readme,
    "- **Current pipeline modularization baseline:** Run241 — batched extraction of candidate identity, note manuscript shaping, gate diagnostics, Screening protocol and Source ROI policy in addition to prior modularized domains",
    "- **Current pipeline modularization baseline:** Run242 — pure Notion payload shaping, source-document parsing and Deferred Deep Dive queue policy extraction layered on prior modularized domains",
    "README baseline",
)
replace_once(
    readme,
    "- `source_roi_policy.py` — canonical zero-model Source ROI smoothing, profile, allocation and run-metric shaping with provider-failure exclusion preserved\n",
    "- `source_roi_policy.py` — canonical zero-model Source ROI smoothing, profile, allocation and run-metric shaping with provider-failure exclusion preserved\n"
    "- `notion_payloads.py` — canonical pure Notion property/page/manuscript payload shaping; Notion API calls and canonical destination resolution remain pipeline-owned\n"
    "- `source_document_parsing.py` — canonical stdlib-only GitHub/arXiv/source-link/HTML parsing and evidence-metadata shaping; network acquisition and SSRF boundaries remain pipeline-owned\n"
    "- `deferred_queue_policy.py` — canonical pure Deferred Deep Dive TTL, identity, serialization, expiry, ranking and capacity policy; persistence and Pending Retry fail-safe remain pipeline-owned\n",
    "README runtime map",
)

spec = Path("AI_Intelligence_Factory_最終仕様書.md")
replace_once(
    spec,
    "Pipeline Modularization Baseline: **Run241 — batched candidate-identity + note-manuscript + gate-reasoning + Screening-protocol + Source-ROI extraction layered on prior zero-quality-change strangler modularization**",
    "Pipeline Modularization Baseline: **Run242 — pure Notion-payload + source-document parsing + Deferred-queue policy extraction layered on prior zero-quality-change strangler modularization**",
    "spec baseline",
)
replace_once(
    spec,
    "- Run241では低リスクな5領域を一括で抽出し、`candidate_identity.py`、`note_manuscript.py`、`gate_reasoning.py`、`screening_protocol.py`、`source_roi_policy.py`を正本化する。Gate実行本体・Gemini実行本体・Notion書込本体・Quota/Pending Retryは移動対象に含めない。`pipeline.py`はlive設定・callbackを渡す薄いwrapperを保持し、12,461行から11,497行へ964行削減する。\n"
    "- Run235/236/237/238/239/240/241はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
    "- Run241では低リスクな5領域を一括で抽出し、`candidate_identity.py`、`note_manuscript.py`、`gate_reasoning.py`、`screening_protocol.py`、`source_roi_policy.py`を正本化する。Gate実行本体・Gemini実行本体・Notion書込本体・Quota/Pending Retryは移動対象に含めない。`pipeline.py`はlive設定・callbackを渡す薄いwrapperを保持し、12,461行から11,497行へ964行削減する。\n"
    "- Run242ではpureなNotion payload組立、source文書/URL/HTML解析、Deferred Deep Dive queue policyを`notion_payloads.py`、`source_document_parsing.py`、`deferred_queue_policy.py`へ抽出する。Notion API書込、network acquisition/SSRF境界、Pending Retry fail-safeは`pipeline.py`に残し、11,497行から11,172行へ325行削減する。\n"
    "- Run235/236/237/238/239/240/241/242はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。",
    "spec run242 contract",
)
replace_once(
    spec,
    "- Run241詳細: `docs/reference/RUN241_BATCHED_PIPELINE_MODULARIZATION.md`\n",
    "- Run241詳細: `docs/reference/RUN241_BATCHED_PIPELINE_MODULARIZATION.md`\n"
    "- Run242詳細: `docs/reference/RUN242_NOTION_SOURCE_DEFERRED_MODULARIZATION.md`\n",
    "spec reference",
)

print("Run242 documentation reconciliation: PASS")
