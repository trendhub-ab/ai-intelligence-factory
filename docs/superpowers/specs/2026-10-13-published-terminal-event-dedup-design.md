# Published Terminal + Event-Aware Dedup Design

Date: 2026-10-13
Status: Design for implementation
Base main: `930178596dfd59ac069c8d3ee5437d594e8be66e`

## 1. Intent

AIIF must stop automatically regenerating an article once that exact article has entered the external publication lifecycle, while still allowing new articles about the same technology when there is a materially new event, claim, release, capability change, deployment, safety finding, or other development.

The system must optimize for:

- protection of already-published or already-delivering assets;
- zero unnecessary model calls for terminal assets;
- maximum new-article Ready yield from the bounded Daily/Fresh model budget;
- continued discovery of genuinely new developments about an existing technology;
- fail-closed behavior when publication/delivery state is ambiguous;
- no weakening of Evidence, Fact, Publication, Reader Value, Human Appeal, or note delivery contracts;
- no Astra-specific exception or URL/page-ID blacklist.

## 2. Incident-derived problem statement

A historical Ready article can currently become eligible for `stale Ready` recovery when the checked-out Publication Contract no longer authenticates its persisted manuscript. `article_revalidation.py` may then select that row in the write-enabled recovery lane. During Ready Rescue, stale Ready is intentionally preferred within a bounded probe.

This creates two risks:

1. a delivered/published asset can consume scarce Daily model budget again;
2. a failed revalidation can demote or otherwise mutate an asset that was already externally published.

The existing note delivery classifier already distinguishes `not_queued`, `waiting`, `already_delivered`, `human_blocked`, and invalid states, and treats `投稿準備中` / `投稿済み` as already delivered. However, publication terminality is not yet a single invariant applied before every automatic generation/recovery path.

## 3. Core invariants

### 3.1 Published/Delivery terminal invariant

For the same article identity:

- `already_delivered`, `published`, or equivalent durable external-delivery evidence is terminal for all automatic generation and recovery lanes.
- Terminal means: no Gemini/model call, no manuscript regeneration, no lifecycle demotion, no automatic content mutation.
- Human/manual operations may still inspect or deliberately supersede an article, but automatic Daily/Fresh/Recovery execution may not.

### 3.2 Pre-publication stale Ready invariant

A Ready article that has **not** entered external delivery may still be revalidated if its persisted manuscript no longer satisfies the current Publication Contract.

- Revalidation remains bounded.
- Failed revalidation must not destroy a usable prior asset.
- Automatic revalidation may mutate only pre-publication assets.

### 3.3 Technology is not article identity

A technology identity (for example a product/model/project family) is broader than an article/story identity.

Published terminality applies to an **article/event identity**, not to the technology as a whole.

Therefore the same Technology ID may legitimately produce multiple published articles:

- initial capability announcement;
- later speed or quality improvement;
- new version/release;
- API/general availability;
- commercial deployment;
- safety/security finding;
- pricing/business-model change;
- material benchmark change;
- policy/regulatory change;
- other materially new decision-relevant development.

### 3.4 Event-aware duplicate invariant

A new candidate is duplicate only when it represents the same material event/claim/development as an already known article, not merely because it shares a Technology ID.

The system must distinguish:

- same technology + same event/claim + paraphrased/reported again -> duplicate;
- same technology + materially new event/claim/development -> new article candidate.

## 4. Identity model

Use two conceptual layers.

### Technology Identity

Stable identity for the continuing subject, such as Astra, Claude Code, Gemini, a framework, platform, or vendor product family.

This identity is useful for grouping, portfolio balance, history, and Rolling Re-review context.

### Story/Event Identity

Identity for one publishable development.

It should be derived from durable signals already available in the pipeline, preferring deterministic evidence over model-only identity:

1. normalized/canonical source URL identity;
2. explicit upstream event/release identifier when available;
3. normalized primary claim/event signature from source metadata/title/evidence;
4. temporal/version/release discriminator when the same source family covers multiple developments.

No single Technology ID is sufficient to mark a candidate duplicate.

The implementation should reuse the existing candidate identity/dedup surfaces where possible rather than introduce a parallel full identity subsystem.

## 5. Terminal-state source of truth

### 5.1 Resolver, not scattered checks

Create one shared **Publication Terminal Resolver** used by automatic generation/recovery lanes.

The resolver should determine terminality from durable external-delivery evidence already present in AIIF, with a conservative precedence order.

Recommended precedence:

1. exact delivery identity bound to the Content Intelligence article (`同期ID` / stable article binding);
2. destination state `投稿準備中` or `投稿済み` -> terminal;
3. durable `note公開URL` / posted identity when available -> terminal;
4. human-blocked state -> automatic generation/recovery blocked;
5. ambiguous/duplicate/invalid delivery state -> fail closed for automatic recovery;
6. no delivery record -> not terminal; pre-publication logic may continue.

A content manuscript caption or Publication Policy SHA is **not** proof that an externally published article should be regenerated. Publication Contract freshness and publication terminality are separate concerns.

### 5.2 No new external database unless required

Prefer the existing durable note delivery/posting records and stable Content Intelligence binding as the authoritative publication terminal evidence. Do not introduce a new Notion database solely for this change unless implementation evidence proves the existing durable records cannot express terminality safely.

This keeps operational cost and schema complexity low.

## 6. Where the terminal guard must apply

The guard must be shared and applied before any automatic model-generating recovery for an existing article, including at minimum:

- normal/full existing article recovery;
- Ready Rescue / stale Ready recovery;
- Pending Retry when the pending item maps to an already-delivered article;
- automatic article revalidation when persistence/mutation is enabled;
- any future automatic lane that regenerates an existing Content Intelligence article.

Fresh/new-candidate discovery is not globally blocked by Technology ID. Its duplicate decision remains event/article-aware.

Read-only audit/validation may inspect terminal articles, but must not write or call a model unless explicitly invoked as a manual diagnostic contract.

## 7. Recovery behavior

### Current-policy Ready

- Terminal in the existing sense; no regeneration.

### Pre-publication stale Ready

- Eligible for bounded revalidation.
- Must pass normal Evidence/Fact/Publication/Human Appeal gates.
- Successful replacement converges to one canonical manuscript using the existing Run194 canonicalization contract.

### Delivered/published stale Ready

- Not eligible for automatic model regeneration.
- Do not demote.
- Do not change article/content status merely because current policy SHA differs.
- Rolling Re-review may evaluate whether a new development exists, but it produces a new update candidate/article rather than rewriting the historical publication automatically.

### Failure handling

For automatic recovery of pre-publication assets:

- provider unavailable / 503;
- budget exhausted;
- Fact/Evidence/Publication gate failure;
- persistence uncertainty;

must remain fail-closed without causing a published/delivered asset to regress.

## 8. Rolling Re-review contract

Rolling Re-review is the correct lane for post-publication evolution.

It should distinguish:

- no material source/evidence/event change -> update review metadata only; model generation 0 when deterministic checks are enough;
- material new event/development -> create a new candidate/story identity;
- correction that requires human editorial action on an already-published article -> flag for explicit human/manual handling, not automatic rewrite.

Published historical bytes remain historical evidence; later policy changes do not silently rewrite them.

## 9. Event-aware acceptance examples

Given Technology ID `Astra`:

- Existing published story: `Astra demonstrates direct robot control`.
- New source repeating the same demonstration with a paraphrased headline -> duplicate, no new article.
- New source: `Astra inference latency drops enough for real-time manipulation` -> new event, eligible new article.
- New source: `Astra API becomes generally available` -> new event, eligible new article.
- New source: `Astra deployed in commercial factory` -> new event, eligible new article.
- New source: `Astra safety evaluation reveals material failure mode` -> new event, eligible new article.

The terminal guard blocks only regeneration of the first published story; it does not suppress the later events.

## 10. Implementation shape

Prefer a small shared module/helper over edits scattered across large `pipeline.py` surfaces.

Expected touch points (exact set determined by TDD exploration):

- `article_revalidation.py` for write-enabled existing-article recovery;
- `note_ready_sync.py` for reuse/export of exact durable delivery-state classification if needed;
- pending-retry / Ready-Rescue orchestration adapters if they can regenerate an existing article before the shared guard runs;
- existing candidate identity/dedup helper(s) for an event-aware regression contract;
- focused tests plus repository contract/guard tests.

Avoid raw `pipeline.py` changes unless no modular overlay/helper can enforce the invariant, because `pipeline.py` is high-coupling and historically participates in frozen/guarded surfaces.

## 11. TDD acceptance tests

Minimum RED tests before production implementation:

### Terminal guard

1. existing article + delivery state `投稿済み` -> automatic recovery selects/generates 0; model call 0.
2. existing article + delivery state `投稿準備中` -> automatic recovery selects/generates 0; model call 0.
3. duplicate delivery rows / unreadable delivery state -> automatic recovery fails closed; model call 0.
4. human-blocked delivery -> automatic recovery 0.
5. `not_queued` stale Ready -> bounded pre-publication recovery remains eligible.
6. `waiting` may follow the existing explicit product contract, but must not be allowed to regress a draft/delivery that has already crossed the durable delivery boundary; tests must pin the exact intended semantics.

### Asset preservation

7. terminal published/delivered article + old Publication Policy SHA -> no status/body mutation.
8. terminal article + provider 503 path -> no mutation.
9. terminal article + Gate changes -> no mutation.

### Event-aware dedup

10. same Technology ID + same canonical event/source identity -> duplicate.
11. same Technology ID + materially distinct event/release identity -> not duplicate.
12. different headline wording for same event -> duplicate when existing deterministic identity signals prove sameness.
13. same technology, later version/release/event -> new candidate remains eligible.

### Regression boundaries

14. Evidence/Fact/Publication/Reader/Human Appeal thresholds unchanged.
15. no new Gemini call for terminal-state classification.
16. Fresh source acquisition and new-event generation remain functional.
17. Run194 one-canonical-manuscript contract remains green.
18. note lossless delivery/durable delivery tests remain green.

## 12. Non-goals

- No Astra-specific suppression.
- No permanent blacklist by source URL, title, page ID, or Technology ID.
- No weakening of stale Ready detection for unpublished inventory.
- No automatic rewrite of already-published note content.
- No new model call to decide whether a terminal existing article is terminal.
- No change to Gemini public-writer model policy in this work.
- No merge without full deterministic regression and repository guards.

## 13. Verification gates

Implementation is mergeable only after:

1. focused RED demonstrates the missing terminal/event contracts;
2. focused GREEN passes;
3. full repository pytest passes;
4. relevant repository falsification/modularization/workflow guards pass;
5. Synthetic Production smoke passes with production write isolation;
6. no Fresh frozen-contract regression;
7. diff proves no gate threshold/model budget/provider-policy weakening;
8. Draft PR shows exact changed files and final head SHA;
9. main remains unchanged until explicit `MERGE GO`.

## 14. Operational outcome

After implementation:

- an already-published Astra article cannot be automatically regenerated by Daily merely because its stored Publication Contract is stale;
- that historical article remains terminal even if local manuscript metadata is later repaired or reorganized;
- a genuinely new Astra development remains eligible as a separate story/article because event identity, not Technology ID alone, drives duplicate suppression;
- model budget is preserved for new or genuinely recoverable pre-publication content.
