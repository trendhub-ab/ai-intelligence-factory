# AI Intelligence Factory V2 Rebuild Design

Date: 2026-10-15
Status: Design specification — awaiting implementation-plan approval
Base Production main: `fd2841a2d8174c75a68548c2f0f60eca2a9dff58`

## 1. Purpose

AIIF V2 is a deliberate rebuild of AI Intelligence Factory that will ultimately replace V1 as Production authority.

The goal is not to reproduce every V1 mechanism. The goal is to preserve only the contracts that protect revenue, evidence quality, publication quality, and delivery safety while removing historical complexity, implicit side effects, duplicated gates, and unnecessary fallback behavior.

V1 remains the current Production system while V2 is developed and proven in isolation.

## 2. Product objective

V2 must improve the business system, not merely the codebase.

The target outcome is:

- higher topic-selection quality;
- stronger evidence traceability;
- more human, useful article output;
- lower provider/API cost per usable article;
- fewer hidden retries and fallbacks;
- smaller and easier-to-audit orchestration;
- fail-closed safety at every authority boundary;
- lossless delivery from Ready candidate to note draft;
- an explicit, measurable path to retire V1.

The rebuild is successful only when V2 can outperform V1 on both business quality and operational simplicity.

## 3. Core strategy

Adopt a **Shadow Sidecar → Measured Promotion → Authority Switch** strategy.

V2 is developed vertically beside V1. It may observe the same live world and produce diagnostic or candidate artifacts, but it receives no Production mutation authority until specific promotion gates are passed.

The migration is intentionally incremental:

1. V2 selects.
2. V2 verifies evidence.
3. V2 creates an article brief.
4. V2 writes.
5. V2 evaluates quality.
6. V2 produces a Ready candidate in shadow.
7. V2 is benchmarked against V1.
8. Only after benchmark success does V2 receive controlled write authority.
9. V2 becomes Production authority only through an explicit authority switch.
10. V1 is then frozen and retired.

There is no Big Bang replacement.

## 4. Architectural principle

V2 is split into two major boundaries.

### 4.1 Intelligence Core

The Intelligence Core determines what is worth publishing and why.

Flow:

`Acquisition → Normalize → Dedupe → Cheap Screening → Ranking → Evidence / Deep Dive → Winner → Article Brief → Writer → Quality Gates → Ready Candidate`

The Core must not directly mutate Notion, note, delivery ledgers, subscriber state, or publication state.

### 4.2 Publication Edge

The Publication Edge takes an already-approved Ready Candidate and performs controlled publishing-side work.

Flow:

`Ready Candidate → Canonical Manuscript → Eyecatch → Notion → note Draft → Delivery Ledger / Receipt`

Publication Edge capabilities are granted only after the Intelligence Core has passed shadow benchmarking.

## 5. Non-negotiable invariants

### 5.1 Production authority

Until the final authority-switch phase:

- V1 remains Production authority.
- V2 must not alter V1 Daily behavior merely because V2 code exists on `main`.
- Presence on `main` does not imply Production execution authority.
- V2 Production mutation requires an explicit later-stage design and approval.

### 5.2 Fail-closed behavior

When evidence, identity, schema, output shape, or delivery state is ambiguous, V2 stops rather than guessing.

No silent repair may convert an unknown state into a successful state.

### 5.3 Side-effect isolation

Core stages communicate through explicit data contracts.

A stage may not silently:

- write another stage's storage;
- invoke a fallback model not declared by its contract;
- re-run another stage;
- publish;
- mutate Notion;
- mutate note;
- change Ready state;
- alter subscriber surfaces.

### 5.4 Bounded provider use

Every provider-backed stage must declare:

- allowed provider/model;
- maximum request count;
- timeout;
- retry count;
- fallback policy;
- accepted output schema;
- failure classification.

Implicit retry or fallback is prohibited.

### 5.5 Canonical identity

Every candidate and every manuscript must have one stable canonical identity.

Duplicate logical content must not create parallel publication paths.

### 5.6 One canonical manuscript

A Ready item has exactly one current canonical manuscript.

Multiple manuscript candidates are a fail-closed state.

### 5.7 Published terminal

Once an item is provably published/delivered, V2 must not automatically regenerate or replace it as if it were pre-publication work.

Recovery is allowed only from a provable pre-publication delivery state.

## 6. What V2 deliberately inherits from V1

V2 inherits contracts, not historical implementation complexity.

The following are retained in principle:

- Evidence / Fact fail-closed discipline;
- stable candidate identity and deduplication;
- one canonical manuscript per Ready item;
- Published Terminal semantics;
- stable note draft identity;
- durable/lossless delivery semantics;
- exact sync identity;
- approved Eyecatch V2 visual contract;
- explicit delivery receipts;
- deterministic safety gates where deterministic logic is sufficient.

These may be reimplemented more simply if the external contract is preserved.

## 7. What V2 does not inherit by default

The following are rejected unless a later design proves they are necessary:

- historical compatibility branches with no current business value;
- duplicated gates that protect the same condition;
- multi-model fallback chains by default;
- automatic rank-2 fallback after rank-1 Deep Dive failure;
- unbounded retries;
- hidden repair logic;
- pipeline-global provider exception handling;
- intermediate Production writes;
- Daily-specific implicit side effects;
- helper code retained only because V1 has it;
- provider-specific behavior leaking into orchestration logic.

YAGNI applies aggressively.

## 8. Existing V2 foundation

The rebuild starts from the V2 work already merged into `main`.

### V2-001 — Shadow Selection Vertical Slice

Established the principle: **V2 selects; V1 writes.**

Provides bounded acquisition interfaces, normalization, deterministic dedupe, provider-free screening, freshness influence, ranking, at-most-one Deep Dive attempt, no rank-2 fallback, fail-closed no-winner behavior, and V1 comparison reporting.

### V2-002 — Bounded Live Shadow Acquisition

Adds bounded read-only live acquisition for shadow observation while preserving Production write isolation.

### V2-003 — Manual Shadow Observation

Adds a manual-only observation path and diagnostic artifact behavior with no scheduled/push Production authority.

### V2-004 — Provider-Backed Evidence

Adds the smallest provider-backed Evidence / Deep Dive slice:

- rank 1 only;
- fixed non-Lite `gemini-3.6-flash`;
- maximum one provider request;
- retry 0;
- fallback 0;
- strict fail-closed structured contract;
- diagnostic output only;
- no Production writes.

### V2-004A/B — Safe Provider Diagnostics

Adds safe machine-readable failure classifications without leaking raw provider response, credentials, prompts, or transport details.

These components are foundations, not Production authority.

## 9. Planned vertical slices

### V2-005 — Live Selection / Evidence Proof

Purpose: prove that the existing selection and Evidence path works on real live candidates before adding Writer complexity.

Required flow:

`Live Sources → V2 Acquisition → Dedupe → Screening → Rank #1 → Gemini Evidence ×1 → Diagnostic Artifact → V1 Comparison`

Scope for V2-005 is intentionally frozen to the currently implemented bounded live acquisition surface. Do not add a new acquisition provider merely to improve a V2-005 result. In particular, use the existing bounded Hacker News / arXiv live path rather than expanding source breadth in this slice.

Constraints:

- no Notion writes;
- no note writes;
- no Ready writes;
- no Production mutation;
- one rank-1 provider-backed Evidence request maximum per live proof run;
- retry 0;
- fallback 0;
- raw provider data must not leak to persisted diagnostics;
- no automatic rank-2 rescue after a failed or insufficient rank-1 Evidence result.

Primary measurements:

1. topic/article value;
2. evidence quality and primary-source traceability;
3. whether V2's winner is better, equivalent, or worse than V1's choice when a V1 comparison is available;
4. whether one provider request is sufficient;
5. provider/API cost per usable winning candidate.

Live proof protocol:

- perform **3 to 5 independent live proof runs** rather than judging from one lucky run;
- each run remains manually initiated and shadow-only;
- persist only safe diagnostic artifacts already allowed by the V2 observation contract;
- record source call counts, candidate counts, rank-1 identity, Evidence result, safe failure code if any, provider call count, budget/cost data available to the workflow, and V1 comparison state where available;
- a `v1_reference_unavailable`-type comparison state is observational, not a reason to fabricate a comparison;
- stop the proof series immediately if any Production mutation, secret/raw-provider leakage, unbounded call behavior, implicit retry, or other P0 invariant violation is observed.

Promotion requirement:

- there is **no automatic numeric promotion** from V2-005 to V2-006;
- after 3 to 5 runs, produce a compact evidence pack summarizing the measurements above;
- the owner/user explicitly decides whether topic value and Evidence quality justify building the Writer lane;
- any P0 invariant violation blocks promotion regardless of apparent content quality.

### V2-006 — Evidence Contract + Article Brief

Purpose: transform verified Evidence into a compact, explicit writing contract.

The Article Brief must separate:

- verified facts;
- source/evidence references;
- allowed inference;
- prohibited unsupported claims;
- target reader value;
- why-now relevance;
- article angle;
- expected takeaway.

The Writer may only write from the Brief plus explicitly permitted evidence inputs.

### V2-007 — V2 Writer

Purpose: produce human-quality prose without giving the model publication authority.

Design intent:

- Local/deterministic logic defines structure, evidence boundaries, and canonicalization.
- A high-quality non-Lite model produces prose, rhythm, explanation, and metaphor where useful.
- The model may not invent Evidence.
- Writer retry/fallback is explicit and bounded.
- No direct Notion/note access.

### V2-008 — Quality / Reader Value Gate

Purpose: decide whether an article is worth a reader's time, not merely whether it is syntactically valid.

Quality evaluation must distinguish:

- factual/evidence safety;
- usefulness;
- readability/naturalness;
- novelty or decision value;
- unsupported hype;
- structural defects.

Hard safety failures remain fail-closed. Soft editorial defects may enter a bounded quality-retry path only if explicitly designed.

### V2-009 — Ready Shadow

Purpose: generate a complete Ready Candidate without Production mutation.

A Ready Candidate must contain everything necessary for later Publication Edge execution, including canonical identity, canonical manuscript, evidence lineage, title, article state, and required presentation metadata.

It remains shadow-only.

### V2-010 — V1 vs V2 Benchmark

Purpose: determine whether V2 deserves Production authority.

Benchmark dimensions:

- Ready yield;
- topic-selection value;
- Evidence quality;
- article quality / reader value;
- human editorial acceptability;
- API/provider cost per usable article;
- model call count;
- total orchestration complexity;
- failure rate;
- ambiguous-state rate;
- delivery readiness.

The benchmark must not be reduced to one numeric score. Safety failures are disqualifying regardless of average quality.

### V2-011 — Controlled Notion Write

Purpose: grant the first narrowly scoped Production mutation capability only after V2 passes the benchmark gate.

Initial write authority must be minimal, explicit, idempotent, and reversible where possible.

No note authority is implied by Notion authority.

### V2-012 — Eyecatch + note Delivery

Purpose: connect the approved Eyecatch V2 and lossless note delivery contracts.

This stage should reuse proven external contracts from V1 rather than reproduce all historical implementation paths.

Required safeguards include stable draft identity, exact sync identity, durable delivery receipt, idempotent recovery, and Published Terminal behavior.

### V2-013 — Production Candidate

Purpose: run V2 as a complete candidate Production path under controlled observation.

V1 still exists as the rollback authority until final cutover.

### V2-014 — Authority Switch

Purpose: explicitly change Production authority from V1 to V2.

This is a deliberate operational event, not an emergent consequence of merging code.

The switch requires a dedicated approval and rollback procedure.

After successful cutover and observation, V1 becomes frozen legacy and is retired in a separate cleanup phase.

## 10. Promotion gates

V2 receives increasing authority only through promotion gates.

### Gate A — Selection / Evidence

Before Writer work is considered complete, live proof must show useful candidate selection and trustworthy Evidence behavior.

Gate A is a human approval gate informed by the V2-005 evidence pack. It is not passed merely because a workflow is GREEN.

### Gate B — Ready quality

Before any Production write authority, V2 must produce shadow Ready Candidates with acceptable reader value and safety.

### Gate C — Benchmark superiority

Before controlled Production writes, V2 must show a clear overall advantage over V1.

Expected direction:

- quality: up;
- cost: down or justified by materially higher value;
- model calls: down or tightly bounded;
- code/orchestration complexity: down;
- hidden failure modes: down;
- safety regressions: zero.

### Gate D — Delivery safety

Before note authority, stable draft identity, lossless delivery, idempotency, and Published Terminal semantics must be proven.

### Gate E — Authority switch

Before V1 retirement, V2 must complete end-to-end Production Candidate proof and have a tested rollback path.

## 11. Cost discipline

V2 is designed for low-cost maximum-value operation.

Rules:

- deterministic/provider-free logic is preferred when it can make the decision reliably;
- model calls happen only where semantic judgment materially improves value;
- every model-backed stage has a maximum call budget;
- retries and fallbacks are explicit, measured, and justified;
- no provider call is made solely to compensate for weak orchestration;
- no Lite model is used for public article prose unless separately approved;
- provider choice may evolve, but the bounded-call contract must remain.

Cost is measured per usable Ready candidate/article, not merely per raw API request.

## 12. Observability

V2 must make its decisions inspectable without leaking sensitive provider data.

Each run should make it possible to determine:

- which sources were called;
- how many candidates entered each stage;
- why candidates were rejected;
- rank order and score/reason components;
- whether Evidence succeeded;
- safe provider failure code when it did not;
- model/provider call counts;
- budget use;
- winner/no-winner decision;
- V1 comparison state while in shadow;
- whether any mutation authority was exercised.

Diagnostics must use safe reason codes rather than raw provider bodies or secret-bearing exception text.

## 13. Testing strategy

Every vertical slice follows TDD and layered verification.

Minimum pattern:

1. focused RED proving the missing behavior;
2. minimum implementation;
3. focused GREEN;
4. relevant integration/regression tests;
5. full deterministic repository tests where appropriate;
6. Production isolation/falsification guards;
7. live proof only after offline behavior is proven.

Live proof is not a substitute for deterministic testing.

No live observation is allowed to silently mutate Production state before its promotion gate.

## 14. V1 operating policy during rebuild

V1 continues to serve current Production and revenue needs.

During V2 development:

- freeze V1 feature growth by default;
- permit V1 changes only for Production-critical defects, security/safety issues, or revenue-critical delivery failures;
- do not port V2 experiments into V1 merely to gain short-term convenience;
- do not connect V2 to Daily until the relevant promotion gate is satisfied;
- continue treating current `main` Production contracts as authoritative for V1.

This prevents the rebuild from becoming another round of V1 complexity growth.

## 15. Migration and rollback

The final migration must be reversible until V2 has demonstrated stable Production behavior.

Authority must be represented explicitly in workflow/configuration, not inferred from code availability.

At cutover:

- one path is the declared Production authority;
- duplicate publication paths are prohibited;
- V1 remains available only as a bounded rollback mechanism for the observation window;
- rollback must not create duplicate drafts/publications;
- identity and delivery receipts must survive authority changes.

## 16. Definition of done for the rebuild

The rebuild is complete when all of the following are true:

- V2 owns candidate selection through delivery;
- V2 has passed live Evidence proof;
- V2 article quality is at least equal to and preferably better than V1;
- V2 cost and model-call budgets are bounded and understood;
- V2 produces exactly one canonical manuscript per Ready item;
- delivery is lossless and idempotent;
- Published Terminal is enforced;
- V2 is measurably simpler to reason about and test than V1;
- V2 is the explicit Production authority;
- V1 is no longer required for normal Daily execution;
- V1 retirement can occur without losing canonical identities, drafts, or delivery history.

## 17. Immediate next step after this design is approved

Create the implementation plan for **V2-005 — Live Selection / Evidence Proof** only.

Do not plan or implement V2-006 through V2-014 in the same development batch.

V2-005 should be the smallest possible next proof, using the already-merged V2-001 through V2-004B foundation and preserving zero Production mutation.

## 18. Merge policy

This design branch does not change Production behavior.

Do not merge design or subsequent implementation work into `main` without the repository's normal verification and an explicit user `MERGE GO` where required by the current operating convention.
