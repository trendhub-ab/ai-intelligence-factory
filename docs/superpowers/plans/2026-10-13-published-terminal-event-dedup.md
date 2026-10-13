# Published Terminal + Event-Aware Dedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make already-delivered/published article identities terminal for every automatic regeneration lane while preserving new-article eligibility for materially new events about the same technology.

**Architecture:** Add one shared zero-provider publication-terminal resolver that reuses exact note delivery identity and fails closed when delivery authority is unavailable or ambiguous. Route write-enabled existing-article recovery and Pending Retry through that resolver before any model reservation. Keep event/article identity separate from Technology identity by preserving the existing deterministic candidate-identity contract and pinning it with regression tests rather than adding a parallel identity subsystem.

**Tech Stack:** Python 3.11, pytest, existing Notion/note delivery helpers, GitHub Actions regression/guard workflows.

**Spec:** `docs/superpowers/specs/2026-10-13-published-terminal-event-dedup-design.md`

## Global Constraints

- Published / already-delivered article identity is terminal for automatic generation and recovery.
- Terminal classification uses zero Gemini/model calls.
- `投稿準備中` and `投稿済み` are terminal.
- `保留`, `取下げ`, duplicate delivery rows, unreadable state, invalid state, and missing delivery authority fail closed for automatic existing-article regeneration.
- `投稿待ち` and no delivery row remain pre-publication states and may use existing bounded recovery policy.
- Technology ID alone must never suppress a materially new event/article.
- No Astra-specific URL/title/page-ID blacklist.
- No Evidence, Fact, Publication, Reader Value, Human Appeal, provider-budget, or public-writer policy weakening.
- Avoid raw `pipeline.py` changes unless a modular enforcement point is proven impossible.
- main remains unchanged until explicit `MERGE GO`.

## Review Focus

- Delivery DB configuration missing in a Daily/ONE-SHOT environment: existing-article regeneration must fail closed, while Fresh/new-candidate generation remains unaffected.
- Duplicate or malformed destination rows: no model call and no mutation.
- Pending Retry item already delivered after it originally entered Pending Retry: skip before provider reservation.
- Same Technology with different OfficialVendor `aif_revision` or materially different canonical event URL: remain distinct candidates.
- Same event with tracking/query presentation differences or repeated cross-source links: remain duplicate under existing canonical identity rules.

---

### Task 1: Shared Publication Terminal Resolver

**Files:**
- Create: `publication_terminal.py`
- Create: `tests/test_publication_terminal.py`
- Reference: `note_ready_sync.py`

**Interfaces:**
- Consumes: `note_ready_sync.classify_exact_delivery_state(sync_id: str) -> str`.
- Produces: `automatic_regeneration_decision(sync_id: str, *, classifier=None, delivery_configured=None) -> tuple[bool, str]`, where the boolean is `allowed` and the reason is stable diagnostic text.

- [ ] **Step 1: Write RED tests for terminal and fail-closed states**

Pin these cases in `tests/test_publication_terminal.py`:

```python
@pytest.mark.parametrize("state", ["already_delivered", "human_blocked", "invalid"])
def test_existing_article_terminal_states_block_automatic_regeneration(state):
    allowed, reason = automatic_regeneration_decision("a" * 32, classifier=lambda _: state, delivery_configured=lambda: True)
    assert allowed is False
    assert reason


def test_missing_delivery_authority_fails_closed():
    allowed, reason = automatic_regeneration_decision("a" * 32, classifier=lambda _: "not_queued", delivery_configured=lambda: False)
    assert allowed is False
    assert reason == "delivery_authority_unavailable"


def test_delivery_read_exception_fails_closed():
    def broken(_):
        raise RuntimeError("unavailable")
    assert automatic_regeneration_decision("a" * 32, classifier=broken, delivery_configured=lambda: True)[0] is False

@pytest.mark.parametrize("state", ["not_queued", "waiting"])
def test_prepublication_states_remain_recoverable(state):
    assert automatic_regeneration_decision("a" * 32, classifier=lambda _: state, delivery_configured=lambda: True)[0] is True
```

- [ ] **Step 2: Run focused tests and prove RED**

Run: `pytest -q tests/test_publication_terminal.py`

Expected: FAIL because `publication_terminal.py` / `automatic_regeneration_decision` does not exist.

- [ ] **Step 3: Implement the minimal resolver**

Create `publication_terminal.py` with:

```python
def automatic_regeneration_decision(
    sync_id: str,
    *,
    classifier: Callable[[str], str] | None = None,
    delivery_configured: Callable[[], bool] | None = None,
) -> tuple[bool, str]:
    ...
```

Requirements:
- lazy-import `note_ready_sync` only when defaults are used;
- `DEST_DATA_SOURCE_ID or DEST_DATABASE_ID` is the default configuration proof;
- only `not_queued` and `waiting` return `allowed=True`;
- every other state, configuration absence, import failure, classifier exception, blank/invalid return fails closed;
- zero network/model work beyond the existing classifier call.

- [ ] **Step 4: Run focused tests and prove GREEN**

Run: `pytest -q tests/test_publication_terminal.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `feat: add fail-closed publication terminal resolver`

---

### Task 2: Enforce Terminality in Ready Rescue / Existing Recovery

**Files:**
- Modify: `article_revalidation.py`
- Modify: `tests/test_run277_article_revalidation.py`
- Reference: `run374_ready_rescue.py`

**Interfaces:**
- Consumes: `publication_terminal.automatic_regeneration_decision(...)` from Task 1.
- Produces: existing `run_existing_editorial_recovery(...)` behavior with terminal candidates skipped before rank increment, source hydration, legal checks, and provider requests.

- [ ] **Step 1: Add RED regression for the current fail-open defect**

Add tests that patch the shared resolver/default delivery authority so that:
- no destination DB configured -> stale Ready candidate is skipped and `generate_intelligence_report` call count is 0;
- `already_delivered` -> skipped with call count 0;
- `human_blocked` / duplicate-invalid / classifier exception -> skipped with call count 0;
- `not_queued` and `waiting` -> current bounded stale Ready recovery remains eligible.

Also assert the guard runs during `_READY_RESCUE_ACTIVE=True`, proving Run374 preflight/final rescue cannot bypass it.

- [ ] **Step 2: Run focused tests and prove RED**

Run: `pytest -q tests/test_run277_article_revalidation.py -k "delivery or recovery or stale_ready"`

Expected: at least the missing-authority case FAILS because current code returns `True` when destination DB configuration is absent.

- [ ] **Step 3: Replace local fail-open logic with the shared resolver**

In `article_revalidation.py`:
- import/use `automatic_regeneration_decision`;
- keep `_automatic_existing_recovery_allowed(...)` as a thin compatibility wrapper if existing tests/importers rely on it;
- log the returned reason;
- remove the current `if not DEST...: return True` behavior;
- do not alter selection priority, stale Ready probe limit, model budget, Gate thresholds, or `run374_ready_rescue.py` request caps.

- [ ] **Step 4: Run focused tests and prove GREEN**

Run: `pytest -q tests/test_publication_terminal.py tests/test_run277_article_revalidation.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `fix: make existing article recovery publication-terminal`

---

### Task 3: Enforce Terminality in Pending Retry Without Touching Fresh

**Files:**
- Modify: `pending_retry_validation.py`
- Create: `tests/test_pending_retry_publication_terminal.py`

**Interfaces:**
- Consumes: `publication_terminal.automatic_regeneration_decision(...)`.
- Produces: `run_pending_retry_lane(...)` skips an existing item whose bound Content Intelligence page is not proven pre-publication before any provider-budget or model reservation.

- [ ] **Step 1: Write RED tests**

Pin:
- already-delivered Pending Retry -> `attempted == 0`, model calls 0;
- missing/unreadable delivery authority -> `attempted == 0`, model calls 0;
- `not_queued` -> existing fast-lane behavior preserved;
- `waiting` -> existing pre-publication behavior preserved;
- item without a durable `notion_page_id` -> fail closed for automatic existing-article retry;
- classification itself does not decrement Pending Retry / Deep Dive / global provider budgets.

- [ ] **Step 2: Run focused tests and prove RED**

Run: `pytest -q tests/test_pending_retry_publication_terminal.py`

Expected: FAIL because `run_pending_retry_lane` currently enters budget/model handling without the shared terminal guard.

- [ ] **Step 3: Add the guard before provider admission**

In `run_pending_retry_lane(...)`:
- extract/validate `notion_page_id` before provider budgets;
- call the shared resolver;
- skip terminal/blocked/unknown candidates without incrementing `attempted`;
- retain the one-article attempt ceiling, provider-send ceiling, model exclusions, and `persist_results=False` contract unchanged.

Do **not** apply this resolver to Fresh/new candidate discovery; it is only for retries of existing article identities.

- [ ] **Step 4: Run focused tests and prove GREEN**

Run: `pytest -q tests/test_publication_terminal.py tests/test_pending_retry_publication_terminal.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `fix: block delivered articles from pending retry regeneration`

---

### Task 4: Pin Event-Aware Dedup and Full-System Regression

**Files:**
- Modify only if RED proves a gap: `candidate_identity.py`
- Create: `tests/test_candidate_event_identity_contract.py`
- Verify: `run194_publication_contract.py`, note delivery tests, Fresh frozen-contract guards.

**Interfaces:**
- Consumes: existing `candidate_identity_urls(repo, canonicalizer=...) -> set[str]`.
- Produces: a regression contract that Technology sameness alone cannot create a duplicate and material event/revision identity remains distinct.

- [ ] **Step 1: Add event-identity characterization/RED tests**

Pin:

```python
def test_same_technology_same_event_is_duplicate_by_canonical_identity():
    # tracking/presentation differences normalize to an overlapping event URL
    assert candidate_identity_urls(a) & candidate_identity_urls(b)


def test_same_technology_distinct_official_revision_is_not_duplicate():
    assert not (candidate_identity_urls(rev1) & candidate_identity_urls(rev2))


def test_same_technology_distinct_material_event_url_is_not_duplicate():
    assert not (candidate_identity_urls(event_a) & candidate_identity_urls(event_b))
```

Use a shared `technology_id` field in fixtures to prove it is grouping metadata only; the identity helper must not collapse on it.

If all three tests are GREEN on baseline, treat them as characterization tests and make **no production change** to `candidate_identity.py`. If a test fails, implement only the smallest deterministic event-identity correction; no model call may be added.

- [ ] **Step 2: Run event identity tests**

Run: `pytest -q tests/test_candidate_event_identity_contract.py`

Expected: GREEN if current Run241/aif_revision behavior already satisfies the design; otherwise capture the exact RED before minimal implementation.

- [ ] **Step 3: Run all focused contracts**

Run:
`pytest -q tests/test_publication_terminal.py tests/test_run277_article_revalidation.py tests/test_pending_retry_publication_terminal.py tests/test_candidate_event_identity_contract.py tests/test_run194_publication_contract.py tests/test_run194_single_canonical_manuscript.py`

Expected: PASS.

- [ ] **Step 4: Run full deterministic regression**

Run: `pytest -q`

Expected: all tests PASS; existing warnings only.

- [ ] **Step 5: Run repository guards and synthetic production smoke**

Run the repository's existing verification workflows/commands that previously gate merges:
- Repository-wide Falsification Guard;
- Integration Reconciliation / deterministic regression;
- Notion Access Policy Guard where touched surfaces require it;
- Workflow Reference Guard;
- Synthetic Production smoke, expected `30/30`, `critical_failures=0`, `production_write_isolation=true`;
- Fresh frozen-contract guard, proving no Fresh semantic surface changed.

Expected: all GREEN.

- [ ] **Step 6: Diff audit**

Verify:
- `pipeline.py` unchanged unless an earlier task proved it unavoidable;
- no Evidence/Fact/Publication/Reader/Human threshold changed;
- no Gemini/provider pool/budget changed;
- no new model call introduced;
- terminal resolver is used only for existing-article regeneration/retry paths;
- same-Technology/new-Event candidates remain eligible.

- [ ] **Step 7: Open Draft PR**

PR body must include:
- root cause: existing recovery guard failed open when delivery authority was not configured/available;
- exact RED evidence;
- final focused/full/guard/synthetic results;
- changed files;
- head SHA;
- explicit statement that main is unchanged and merge requires `MERGE GO`.

- [ ] **Step 8: Final verification before claiming completion**

Re-fetch PR head and latest main. Confirm head is the tested SHA, main has not changed unexpectedly, PR is mergeable or explain conflicts, and every required check corresponds to the final head.
