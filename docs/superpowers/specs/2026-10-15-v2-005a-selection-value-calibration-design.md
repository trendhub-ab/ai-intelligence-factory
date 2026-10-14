# V2-005A Selection Value Calibration Design

## Status

Approved design for implementation. This slice is bounded to V2 shadow selection only. It does not change Production authority.

## Purpose

Improve V2 candidate ordering so the system distinguishes:

1. **Evidence readiness** — whether a candidate has enough stable metadata to be evaluated safely; and
2. **Selection value** — whether the candidate is likely to be useful and compelling for AIIF readers.

The current V2-001 `screening_score` mixes completeness/freshness signals with ordering. Long descriptions can therefore outrank shorter but more decision-relevant AI developments. V2-005A separates those concerns without adding model calls or hard gates.

## Scope

Change only the V2 shadow-selection ranking layer.

### In scope

- Preserve the existing `screening_score` and `eligible` semantics.
- Add deterministic provider-free `selection_value_score` and `selection_value_reasons`.
- Rank eligible candidates by Selection Value first, then existing screening score, then stable identity.
- Surface Selection Value in the existing safe screening diagnostic output.
- Add focused tests for calibration, determinism, and regression safety.

### Out of scope

- New acquisition providers.
- Gemini/model pre-ranking.
- New hard gates.
- Changes to `DEFAULT_MIN_SCREENING_SCORE`.
- Changes to the existing Deep Dive request budget.
- Rank-2 fallback.
- Model fallback or retry.
- V2 Writer, Ready, Notion, note, delivery, subscriber, economic, publication, or Production mutations.
- Changes to V1 Production authority.

## Source Portfolio Boundary

V2-005A intentionally leaves the current V2 live-shadow acquisition surface unchanged: **Hacker News + arXiv only**. This is a bounded implementation constraint for this slice, not the target V2 source portfolio.

The target V2 source portfolio remains aligned with the Production Intelligence Source Contract:

1. **OfficialVendor** — vendor primary information
2. **GitHub** — implementation / OSS movement
3. **Hacker News** — discovery / developer reaction
4. **ArXiv** — research / emerging technology

`X` remains optional discovery-only and is not Evidence authority. Product Hunt remains retired from the active Production source portfolio.

After V2-005A is verified, the next bounded slice is **V2-005B Source Portfolio Expansion**, which adds OfficialVendor and GitHub to the V2 shadow acquisition path without changing V1 Production authority. Only after that expansion should the 3–5 run cross-source Live Proof be treated as representative enough to decide whether V2-006 may proceed.

## Invariants

- HN + arXiv acquisition remains unchanged **within V2-005A only**.
- `screening_score` remains Evidence-readiness oriented and keeps its current behavior.
- Default eligibility threshold remains `40`.
- Rank #1 is still the only candidate eligible for Evidence Deep Dive.
- Gemini model remains exactly `gemini-3.6-flash` where V2-005 provider-backed Evidence is invoked.
- Provider Evidence budget remains at most one request per run.
- Retry = 0.
- Model fallback = 0.
- Rank fallback = 0.
- No additional Gemini/provider call is introduced by V2-005A.
- V1 remains Production authority.

## Design

### 1. Evidence Readiness

Existing `screen_candidate()` remains the authority for Evidence readiness:

- stable identity
- title presence
- description completeness
- freshness
- official-source signal where applicable

This score remains `screening_score` and continues to determine `eligible`.

### 2. Selection Value

Add a deterministic function:

```python
def score_selection_value(candidate: Mapping[str, Any]) -> tuple[int, list[str]]:
    ...
```

It must use only already-normalized candidate text fields (`title`, `description`) and must perform no I/O or model call.

The score is additive and intentionally small. It represents four independent value dimensions:

1. **AI relevance**
   - Examples: AI, artificial intelligence, LLM, large language model, foundation model, language model, AI model, agent, inference, robotics, multimodal, reasoning, neural network.
   - Bare `model` must **not** count by itself because phrases such as `business model` would create false positives.
2. **Decision value**
   - Examples: API, pricing, cost, enterprise, security, privacy, regulation, policy, deployment, availability, launch.
3. **Change / novelty**
   - Examples: launch, release, update, new, introduces, acquisition, partnership, policy change, benchmark/result improvement.
4. **Applied / reader value**
   - Examples: workflow, productivity, coding, automation, integration, tool use, implementation, business use, customer/user impact.

Each dimension contributes at most one fixed bonus so repeated keywords do not inflate the score. Matching is case-insensitive and deterministic.

Provider identity itself must not add or subtract Selection Value. In particular, arXiv is not penalized and Hacker News is not rewarded simply for being the source.

A research item may outrank a news item when its text shows clear applied/decision value. Conversely, a long specialist abstract with little AIIF decision value should not win solely because its description is long.

### 3. Ranking

For eligible candidates, ranking order becomes:

1. `selection_value_score` descending
2. `screening_score` descending
3. `candidate_identity` ascending

Candidates remain deterministically ordered.

`screening_score` continues to determine eligibility. Selection Value is **not** a hard gate.

### 4. Diagnostics

Each screened candidate report gains only:

- `selection_value_score`
- `selection_value_reasons`

Do not add raw prompts, provider responses, secrets, headers, full external payloads, or new mutation-capable fields.

## Acceptance Scenarios

### A. Specialist research vs high-value product change

Given:

- Candidate A: long, highly specialist AI research abstract with little applied or decision value.
- Candidate B: shorter AI product/API development with material pricing, availability, or enterprise impact.

Expected: both may remain eligible, but B ranks above A because its `selection_value_score` is higher.

### B. Applied research can still win

An arXiv candidate describing a material inference-cost reduction, practical implementation, or deployable capability may outrank a generic news item.

### C. Non-AI business news does not win from business language alone

Business terms such as price, enterprise, partnership, launch, or `business model` must not be enough to produce a high-value score unless AI relevance is also present.

### D. Determinism

The same candidate set must produce the same scores, reasons, and ordering across repeated executions.

### E. Existing safety contract

- network calls added by this slice: `0`
- model calls added by this slice: `0`
- hard gates added: `0`
- Production mutations added: `0`

## Implementation Boundary

Expected files:

- Modify `v2_shadow_selection.py`
- Modify `tests/test_v2_shadow_selection.py`

Do not touch acquisition adapters in V2-005A. OfficialVendor/GitHub expansion belongs to V2-005B as a separate bounded change.

Do not touch downstream writer/delivery modules unless an unrelated pre-existing defect prevents regression verification; in that event, stop and redesign rather than broadening this slice.
