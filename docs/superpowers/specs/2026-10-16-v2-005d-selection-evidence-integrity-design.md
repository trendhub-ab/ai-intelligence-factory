# V2-005D Selection + Evidence Integrity Design

## Status

Approved-for-implementation bug-fix design for the V2 shadow path only. V1 remains the sole Production authority.

## Purpose

Repair two defects exposed by the five-run V2-005 Live Proof without adding network/model calls or changing Production authority:

1. **Cross-source Selection Value distortion** — metadata-rich GitHub releases can outrank materially larger OfficialVendor developments because Selection Value currently allows description text to establish AI relevance, while OfficialVendor live candidates often have title-only metadata.
2. **Evidence grounding contamination** — the Gemini Evidence prompt currently includes AIIF internal `screening_score` and `screening_reasons`, allowing internal evaluation metadata to be returned as an evidence point.

## Root Cause

### Selection

`score_selection_value()` ranks by text content only and currently combines `title + description` before establishing AI relevance. The four live sources do not provide comparable description richness:

- OfficialVendor live reader: article title, empty description, no timestamp when the collection page does not expose one through the current parser.
- GitHub live reader: release title plus full release body and published timestamp.
- Hacker News: story title plus engagement metadata description.
- arXiv: paper title plus abstract.

The effect is structural: a generic GitHub version title such as `v3.28.0` can borrow AI/decision/applied terms from a long release body and score highly, while a major branded-model announcement can score zero when its title lacks the current generic AI keywords.

### Evidence

`build_deep_dive_prompt()` includes `screening_score` and `screening_reasons` in the candidate payload. Because the provider is instructed to use only supplied metadata, those internal fields are currently valid prompt-grounded material and can be returned as `evidence_points` even though they are not source evidence.

## Goals

- Keep cross-source ranking deterministic and provider-free.
- Require the candidate title itself to establish that the topic is AI-relevant before description text may add decision/change/applied value.
- Recognize the major branded AI model/product names present in the approved source portfolio: `GPT`, `ChatGPT`, `Claude`, `Gemini`.
- Preserve description-assisted scoring for applied research and other candidates whose titles already establish AI relevance.
- Prevent generic version labels from becoming high-value candidates only because their descriptions are long/rich.
- Remove internal ranking/screening fields from the Gemini Evidence prompt.
- Preserve max one Evidence request, retry 0, model fallback 0, rank fallback 0.
- Add network calls: 0.
- Add model calls: 0.
- Add hard gates: 0.
- Add Production mutations: 0.

## Non-goals

- No OfficialVendor detail-page crawling or extra GETs.
- No source-family bonus or penalty in Selection Value.
- No change to `screening_score`, `DEFAULT_MIN_SCREENING_SCORE`, or eligibility semantics.
- No new model-based pre-ranking.
- No V2 Writer, Ready, Notion, note, delivery, subscriber, economic, or publication mutation.
- No new Live Proof run under the completed five-run V2-005 protocol.

## Design

### 1. Title-grounded AI relevance

`score_selection_value(candidate)` continues to use normalized `title` and `description` and keeps the existing four 15-point dimensions / 60-point maximum.

Change only the AI-relevance precondition:

- AI relevance must match in **title tokens**.
- If title AI relevance is absent, return `(0, [])` immediately, even if description contains AI terms.
- Once title AI relevance is established, decision/change/applied dimensions may match across `title + description` as before.

This preserves source-family neutrality while preventing metadata-rich descriptions from creating the topic identity of an opaque candidate.

### 2. Branded AI title vocabulary

Extend AI-relevance terms with exact token-aware matches for:

- `gpt`
- `chatgpt`
- `claude`
- `gemini`

Do not add broad company names such as `google` or generic bare `model`.

Also add common announcement morphology needed by official titles to the existing change/novelty vocabulary where absent: `introducing`, `announcing`, `launched`, `launches`.

### 3. Evidence source-only payload

`build_deep_dive_prompt(candidate)` must exclude AIIF-internal evaluation fields.

Allowed prompt payload fields remain source/provenance metadata already acquired before Evidence:

- `provider`
- `primary_url`
- `title`
- `description`
- `source_timestamp`

Explicitly forbidden from the Evidence prompt:

- `screening_score`
- `screening_reasons`
- `selection_value_score`
- `selection_value_reasons`
- rank/order metadata

Prompt copy must state that evidence points are source-grounded factual claims and must not cite internal scores/ranking/pipeline metadata.

## Acceptance Scenarios

### A. Major official model announcement beats opaque SDK version release

Given:

- OfficialVendor title `GPT-6 for everyone`, empty description.
- GitHub title `v3.28.0`, long release body containing `agent`, `API`, `deployment`, `workflow`, `release` terms.

Expected:

- Official candidate has positive Selection Value from title AI relevance.
- Generic GitHub version candidate has Selection Value `0` because the title does not establish AI relevance.
- Official candidate ranks above the GitHub candidate even when GitHub has a higher `screening_score` from richer metadata.

### B. Applied research remains competitive

Given an arXiv title that establishes AI relevance and an abstract containing material cost/deployment/implementation improvements, description terms may still raise its decision/change/applied dimensions.

### C. Generic body cannot manufacture AI relevance

A candidate titled only `v3.28.0` returns Selection Value `0` even if its description is packed with AI/agent/API/deployment terms.

### D. Brand recognition is token-aware

`GPT`, `ChatGPT`, `Claude`, and `Gemini` titles establish AI relevance; unrelated substrings do not.

### E. Evidence prompt excludes internal evaluation

A candidate containing screening fields produces a prompt with none of `screening_score`, `screening_reasons`, `selection_value_score`, `selection_value_reasons` and contains only the allowed source/provenance payload fields.

### F. Safety invariants remain unchanged

- V1 Production authority.
- Evidence request budget <= 1.
- Retry 0.
- Model fallback 0.
- Rank fallback 0.
- Production mutation false.

## Expected Files

- Modify `v2_shadow_selection.py`
- Modify `tests/test_v2_shadow_selection.py`
- Modify `v2_shadow_observation.py`
- Modify `tests/test_v2_shadow_deep_dive.py`
- Update canonical Production contract fingerprint only if the repository guard requires it after code changes.

No acquisition adapter should change in V2-005D.