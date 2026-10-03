# P0-A Note Lossless Delivery Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace heuristic note-body integrity checks with a deterministic, model-free canonical document contract that proves the approved note presentation survives renderer, note save, and reopen without semantic or structural corruption.

**Architecture:** Build a pure-Python canonical document layer first, with source Markdown parsing, safe HTML projection, structural comparison, and fail-closed unsupported syntax. Then add a thin browser adapter to the existing Run291/292 read-only private-draft audit so actual saved note DOM is converted independently into the same canonical model. Only after one real private draft proves the DOM mapping and every legitimate note normalization is frozen by evidence-backed fixtures will production draft creation/save/reopen switch from coarse text heuristics to mandatory canonical equality.

**Tech Stack:** Python 3.11, stdlib `dataclasses` / `html.parser` / `unicodedata` / `hashlib`, existing Playwright-based note audit, `unittest`/Pytest-compatible test suite, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-03-note-lossless-delivery-contract-design.md`

## Global Constraints

- Design baseline is `13454791d35a06a0bc1c7dfbe99478e9ebb7176f`; rebase/recheck latest `main` before implementation if it advances.
- Expected content is derived only from the current Publication Contract manuscript after the approved deterministic Run222 note-presentation transform.
- Actual note DOM must never define, mutate, or widen the expected representation.
- No Gemini/OpenAI/other model call may participate in integrity verification.
- Unknown Markdown constructs and unknown note DOM constructs fail closed; no silent plain-text flattening.
- Numbers, negation, units, entity/product names, comparison targets, URLs, code, ordered content, and editorial structure are exact contract material.
- No public-release automation is added or changed.
- No raw unpublished manuscript, private DOM, draft URL, screenshot, browser storage state, cookie, or arbitrary exception text may enter public Actions logs, summaries, annotations, or artifacts.
- Evidence, Fact, Human Appeal, Publication, current-publication-contract, image-proof, exact-sync-id, and current-run causality rules remain unchanged.
- N01 durable delivery idempotency is explicitly out of scope; a canonical PASS does not make create/queue update atomic.
- Phase 1-3 must not change production acceptance behavior. Phase 4 starts only after the read-only real-DOM evidence gate passes.
- No new runtime dependency is added unless the stdlib implementation proves insufficient and the change is separately reviewed.

## Review Focus

1. **Markdown-looking characters inside code and links:** backticks, asterisks, brackets, parentheses, `#`, `-`, and `>` inside code/URL/text must not be reinterpreted as structure; Task 1 and Task 2 pin this with parser/round-trip tests.
2. **Nested or mixed lists and continuation lines:** if the supported grammar cannot preserve them unambiguously, delivery must reject them rather than flattening; Task 1 pins unsupported/mixed-list behavior and Task 4 can only widen support with real evidence plus fixtures.
3. **Unicode edge cases:** combining marks, Japanese full-width text, emoji, and visually similar characters must not be broadly normalized into equality; Task 1 pins NFC-only prose behavior and mismatch cases.
4. **Browser/editor wrapper churn:** harmless note wrapper changes must not trigger content disclosure or accidental PASS; Task 3 inventories structure content-free, and Task 4 allows only named evidence-backed wrapper normalization.
5. **Save/reopen divergence after initial paste:** a body that matches immediately after paste but changes after reopen must fail the canonical gate and must not advance the queue; Task 5 pins both insertion and persistence verification paths.

---

## File Structure

### New files

- `note_document_contract.py` — pure canonical node model; approved-presentation Markdown parser; safe HTML renderer; safe HTML parser; canonical normalization/comparison; version constants; content-free mismatch receipt.
- `note_document_dom.py` — browser-boundary adapter only: extract a content-bearing but in-memory semantic DOM snapshot from an existing note body locator and convert it to canonical nodes under an explicit note DOM policy. It never logs or persists raw DOM/text.
- `tests/test_note_document_contract.py` — pure offline positive, negative, adversarial, unsupported-syntax, Unicode, and safe-HTML round-trip tests.
- `tests/test_note_document_dom.py` — DOM snapshot conversion, unsupported-node, privacy, and wrapper-policy tests using synthetic snapshots/mocked locators only.

### Modified files

- `run292_note_rendered_body_audit.py` — replace visible-text-only audit acceptance with canonical expected/actual comparison for the read-only audit path; retain only content-free diagnostics.
- `tests/test_run292_note_rendered_body_audit.py` — RED tests for canonical audit integration, privacy, mismatch categories, and unsupported DOM.
- `.github/workflows/note-private-draft-audit.yml` — invoke new tests and expose only allow-listed structural/categorical metrics if needed.
- `note_draft_automation.py` — Phase 4 only: route Markdown rendering through the canonical renderer and require canonical equality after paste and after reopen before queue advancement.
- `tests/test_note_draft_automation.py` — Phase 4 production-path RED tests proving semantic corruption and unsupported content block delivery.
- `tests/test_run417_note_content_verification.py` or the effective Run417 test file discovered at execution time — prove the effective production verification path cannot fall back to anchor/length acceptance.
- `run222_note_presentation_integrity.py` — modify only if tests prove the approved presentation transform itself violates the canonical contract; otherwise leave unchanged.

---

### Task 1: Pure Canonical Document Model, Parser, and Comparator

**Files:**
- Create: `note_document_contract.py`
- Create: `tests/test_note_document_contract.py`

**Interfaces:**
- Consumes: approved note-presentation Markdown produced by existing Run222.
- Produces:
  - `CONTRACT_VERSION: str`
  - `NORMALIZATION_POLICY_VERSION: str`
  - `CanonicalContractError(Exception)` with fixed `code: str`
  - immutable node types for `Document`, `Heading`, `Paragraph`, `OrderedList`, `UnorderedList`, `ListItem`, `CodeBlock`, `InlineCode`, `Link`, `Strong`, `Emphasis`, `BlockQuote`, `Divider`, `Text`, `HardBreak`
  - `parse_presentation_markdown(markdown_text: str) -> Document`
  - `normalize_document(document: Document, *, normalization_codes: tuple[str, ...] = ()) -> Document`
  - `compare_documents(expected: Document, actual: Document) -> dict[str, object]` returning content-free fields including `canonical_match`, `mismatch_category`, `mismatch_path`, and version IDs.

- [ ] **Step 1: Write RED tests for the supported AIIF Markdown surface**

Add tests named for H2-H4 headings, paragraphs, authored hard breaks, unordered lists, ordered lists including a non-1 start, blockquotes, divider, fenced code, inline code, strong, emphasis, exact HTTP/HTTPS link destination, Japanese text, emoji, and NFC-equivalent prose.

Assertions must compare canonical node structure and values, not rendered plain text.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: FAIL because `note_document_contract` and the declared interfaces do not yet exist.

- [ ] **Step 3: Implement the immutable node model and `parse_presentation_markdown()` minimally**

Parsing rules must be explicit and deterministic. Unsupported Markdown must raise `CanonicalContractError(code="unsupported_markdown")`; do not fall back to ordinary paragraph text when syntax is ambiguous.

- [ ] **Step 4: Run positive parser tests and verify GREEN**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: supported parser tests PASS; adversarial/comparator tests added next may still be absent.

- [ ] **Step 5: Write RED adversarial comparator tests**

Add one failing test for each required mutation: negation flip, number change, unit change, product/entity change, comparison target change, link href change, list reorder, list add/delete, ordered-list start change, heading-level change, paragraph add/delete/duplicate, code character change, code indentation/whitespace change, inline-code flattening, quote flattening, unexpected H1, internal `ARTICLE` marker injection, unsupported Markdown, and mixed/nested-list input that the grammar does not explicitly support.

Each mutation must assert `canonical_match is False` or fixed fail-closed error code; no test may accept a ratio/threshold.

- [ ] **Step 6: Run adversarial tests and verify RED**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: comparator-related tests FAIL until deterministic comparison and marker guards exist.

- [ ] **Step 7: Implement `normalize_document()` and `compare_documents()`**

Use only the spec-approved offline-safe normalization: newline canonicalization before parsing and fixed Unicode canonical normalization for ordinary prose. Do not normalize code whitespace, list numbering, URLs, full-/half-width characters, or punctuation changes.

`compare_documents()` must never include node text or URLs in its returned receipt; mismatch location is index/path only.

- [ ] **Step 8: Run the full Task 1 file and verify GREEN**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: all Task 1 tests PASS with zero network/model access.

- [ ] **Step 9: Commit**

```bash
git add note_document_contract.py tests/test_note_document_contract.py
git commit -m "feat: add canonical note document contract"
```

---

### Task 2: Canonical Safe-HTML Projection and Offline Round Trip

**Files:**
- Modify: `note_document_contract.py`
- Modify: `tests/test_note_document_contract.py`
- Read/compare only: `note_draft_automation.py` current `_markdown_to_safe_html()`

**Interfaces:**
- Consumes: `Document` from Task 1.
- Produces:
  - `render_safe_html(document: Document) -> str`
  - `parse_safe_html(html_text: str) -> Document`
  - round-trip invariant `parse_safe_html(render_safe_html(doc)) == normalize_document(doc)` for every supported construct.

- [ ] **Step 1: Write RED round-trip tests for every supported canonical node**

Include special cases from Review Focus: Markdown metacharacters inside code, inline code, link labels, and URLs; code blank lines/indentation; non-1 ordered-list start; hard break; Unicode combining marks.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: FAIL because canonical HTML projection/parsing is not implemented.

- [ ] **Step 3: Implement `render_safe_html()` from canonical nodes, not regex rescanning of Markdown**

Escape text/attributes deterministically. Only `http`/`https` links are supported. Unsupported link schemes fail before rendering rather than being silently rewritten into prose.

- [ ] **Step 4: Implement `parse_safe_html()` with a strict tag/attribute allowlist**

Allowed semantic tags correspond only to canonical nodes. Unknown semantic tags or ambiguous nesting raise `CanonicalContractError(code="unsupported_safe_html")`.

- [ ] **Step 5: Run round-trip tests and verify GREEN**

Run: `python -m pytest tests/test_note_document_contract.py -q`

Expected: all parser/comparator/HTML round-trip tests PASS.

- [ ] **Step 6: Add compatibility tests against the current AIIF renderer without switching production**

For representative current AIIF presentation fixtures, feed the same Markdown to legacy `note_draft_automation._markdown_to_safe_html()` and the new canonical renderer, parse both HTML outputs canonically, and assert canonical equality. If a current construct differs semantically, stop and classify it as a renderer defect or unsupported construct; do not alter production in this task.

- [ ] **Step 7: Run the focused suite and confirm production code is unchanged**

Run: `git diff -- note_draft_automation.py run222_note_presentation_integrity.py`

Expected: no production diff from Task 2.

Run: `python -m pytest tests/test_note_document_contract.py tests/test_note_draft_automation.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add note_document_contract.py tests/test_note_document_contract.py
git commit -m "test: prove canonical safe html round trip"
```

---

### Task 3: Read-Only Note DOM Adapter and Canonical Run292 Audit

**Files:**
- Create: `note_document_dom.py`
- Create: `tests/test_note_document_dom.py`
- Modify: `run292_note_rendered_body_audit.py`
- Modify: `tests/test_run292_note_rendered_body_audit.py`
- Modify only if metric invocation requires it: `.github/workflows/note-private-draft-audit.yml`

**Interfaces:**
- Consumes from Task 1: `Document`, `compare_documents()`, version constants.
- Produces:
  - `snapshot_note_body(body_locator: object) -> dict[str, object]` — one browser `evaluate()` that returns a transient semantic tree only to Python memory.
  - `document_from_note_snapshot(snapshot: dict[str, object], *, allowed_normalizations: tuple[str, ...] = ()) -> Document`
  - `canonical_audit_metrics(body_locator: object, expected_markdown: str) -> dict[str, object]` in Run292 or a small helper, returning only allow-listed, content-free metrics.

- [ ] **Step 1: Write RED synthetic DOM-snapshot tests**

Cover semantic tags matching canonical nodes plus wrapper-only containers. Include unknown tag, unknown link scheme, missing `href`, changed list order/start, flattened inline code, and code whitespace mutation.

Synthetic snapshots may contain fixture text in test memory; production diagnostics must not return it.

- [ ] **Step 2: Write RED privacy/source-inspection tests**

Assert browser adapter/audit code contains no `.click(`, `.fill(`, `keyboard.press`, paste, save, screenshot, Notion PATCH, public-release action, or arbitrary `print(raw_dom)`/`outerHTML` logging path.

Assert a mismatch result contains no keys such as `actual_text`, `expected_text`, `manuscript`, `raw_dom`, `draft_url`, `href`, or title.

- [ ] **Step 3: Run Task 3 tests and verify RED**

Run: `python -m pytest tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py -q`

Expected: FAIL because DOM canonicalization is not implemented and Run292 still uses visible-text heuristics.

- [ ] **Step 4: Implement `snapshot_note_body()` as a read-only semantic snapshot**

The browser JavaScript may read tag names, child order, authored text nodes, exact link hrefs, ordered-list start, and code text needed for in-memory comparison. It must not write DOM, trigger events, persist snapshots, or print snapshot contents.

Keep browser-specific code in `note_document_dom.py`; keep canonical semantics in `note_document_contract.py`.

- [ ] **Step 5: Implement initial strict DOM mapping with no speculative note-specific normalization**

Map only semantically unambiguous tags and explicitly wrapper-only elements already proven by synthetic contract tests. Anything else raises `CanonicalContractError(code="unsupported_note_dom")`.

- [ ] **Step 6: Replace Run292 acceptance with canonical comparison for the read-only audit only**

`_body_text_metrics()` may remain as secondary diagnostics, but `audit_passed` must require `canonical_match is True`. Anchor/length/footer heuristics cannot override a canonical mismatch or unsupported node.

Safe result fields include only: `canonical_match`, node counts, unsupported counts, normalization codes, mismatch category/path, contract/policy versions, plus existing non-content read-only flags.

- [ ] **Step 7: Run Task 3 tests and verify GREEN**

Run: `python -m pytest tests/test_note_document_dom.py tests/test_run291_private_draft_audit.py tests/test_run292_note_rendered_body_audit.py tests/test_run293_private_draft_guard_diagnostics.py tests/test_run294_note_eyecatch_persistence_diagnostics.py tests/test_run295_note_eyecatch_persistence.py -q`

Expected: PASS; no browser/network/model call in unit tests.

- [ ] **Step 8: Verify workflow remains read-only and P0-C-safe**

Run static assertions/tests that `.github/workflows/note-private-draft-audit.yml` still has zero draft creation/publication path and emits no raw body/DOM/draft URL/image URL.

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add note_document_dom.py tests/test_note_document_dom.py run292_note_rendered_body_audit.py tests/test_run292_note_rendered_body_audit.py .github/workflows/note-private-draft-audit.yml
git commit -m "feat: add read-only canonical note DOM audit"
```

---

### Task 4: Real Private-Draft Evidence Gate and Frozen Normalization Policy

**Files:**
- Modify: `note_document_contract.py` and/or `note_document_dom.py` only for evidence-backed named normalization rules.
- Modify: corresponding tests.
- Modify: design/decision documentation only if evidence identifies note behavior that must be recorded.

**Interfaces:**
- Consumes: Task 3 read-only audit and one exact current Ready / 投稿準備中 existing private draft.
- Produces: evidence-backed named normalization codes and regression fixtures; no production verifier change yet.

- [ ] **Step 1: Recheck the target is exactly one current Ready / 投稿準備中 row and has no public-post evidence**

Use the existing Run291 preflight contract. Do not choose a public article or create a replacement draft.

Expected: preflight returns `audit_ready`, `read_only=true`, `zero_gemini_calls=true`, `draft_mutation=false`.

- [ ] **Step 2: Run the existing private-draft audit workflow read-only with canonical metrics enabled**

No Daily, Fresh, Rolling Re-review, model call, note write, Notion write, screenshot artifact, or public release is permitted.

Expected outcomes are intentionally binary:
- complete supported mapping and canonical match, or
- fail-closed `unsupported_note_dom`/specific mismatch category with content-free structural metrics.

- [ ] **Step 3: If unsupported legitimate note structures are observed, write RED fixtures before adding a normalization/mapping**

Each new rule must have a stable name such as `note_wrapper_transparent_v1` or another evidence-specific code. The test must prove the exact legitimate transformation passes while nearby semantic mutations remain failures.

Do not add a catch-all `div`/whitespace/text normalization merely to make the real draft pass.

- [ ] **Step 4: Implement only the minimum evidence-backed mapping/normalization and rerun offline tests**

Run: `python -m pytest tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py -q`

Expected: PASS, including negative mutation neighbors.

- [ ] **Step 5: Re-run the read-only real draft audit**

Expected before Phase 4 can begin:
- `canonical_match=true`
- unsupported expected/actual node counts are zero
- every applied note normalization code has a committed fixture and rationale
- no unpublished content appears in public logs/summary/artifacts.

If not all conditions hold, **STOP**. Phase 4 is NO-GO and production note acceptance remains unchanged.

- [ ] **Step 6: Commit the frozen policy/evidence fixtures**

```bash
git add note_document_contract.py note_document_dom.py tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py docs/superpowers/specs/2026-10-03-note-lossless-delivery-contract-design.md
git commit -m "test: freeze evidence backed note normalization policy"
```

---

### Task 5: Production Renderer and Save/Reopen Canonical Gate

**Precondition:** Task 4 exit criteria are all satisfied. If not, this task must not start.

**Files:**
- Modify: `note_draft_automation.py`
- Modify: `tests/test_note_draft_automation.py`
- Modify: effective Run417 note-content verification module/test discovered on latest main, if that layer wraps the same acceptance path.
- Modify only if required by the current composition: `run194_note_persistent_cloud.py` or its effective installer/wrapper.

**Interfaces:**
- Consumes: `parse_presentation_markdown()`, `render_safe_html()`, `snapshot_note_body()`, `document_from_note_snapshot()`, `compare_documents()`.
- Produces: production note draft paste/save/reopen acceptance that cannot succeed unless canonical equality passes.

- [ ] **Step 1: Write RED production-path tests for semantic corruption**

Patch/mock the body snapshot after insertion and after reopen separately. For each boundary, mutate number, negation, unit, entity, href, list order/start, heading level, inline code, and code whitespace.

Assert `_verify_body_content()` or its replacement raises `NoteDraftError` and `_mark_draft_created()` is not reached.

- [ ] **Step 2: Write RED unsupported-source and unsupported-DOM tests**

Assert delivery blocks before queue advancement when the approved presentation contains unsupported Markdown or readback contains unsupported DOM.

- [ ] **Step 3: Write RED save/reopen divergence test from Review Focus**

Initial post-paste snapshot is canonical-equal; reopened snapshot differs by one semantic value. Assert draft verification fails after reopen and queue state is not advanced.

- [ ] **Step 4: Run production focused tests and verify RED**

Run: `python -m pytest tests/test_note_draft_automation.py tests/test_run417_note_content_verification.py -q`

If the Run417 filename differs on current main, use the discovered effective test file and record it in the commit/PR.

Expected: new canonical-gate tests FAIL under the current coarse verifier.

- [ ] **Step 5: Route production safe HTML through the canonical renderer**

Keep `_markdown_to_safe_html(markdown_text: str) -> str` as a compatibility interface if other code imports it, but make it parse the already-approved presentation Markdown into canonical form and render from canonical nodes. Unsupported syntax raises `NoteDraftError` via a fixed safe category.

Do not change Run222 semantics in this step.

- [ ] **Step 6: Replace `_verify_body_content()` acceptance with canonical DOM equality**

The function may retain coarse visible metrics as diagnostics, but those metrics can never turn a canonical mismatch into PASS. Use the same mandatory gate immediately after paste and after reopen in `_save_draft_and_verify()`.

- [ ] **Step 7: Ensure queue advancement depends on successful reopened canonical verification**

Inspect the effective call chain and assert `_mark_draft_created(destination_page_id)` happens only after `_create_browser_draft()` returns from save/reopen canonical verification. Do not attempt to solve N01 crash idempotency here.

- [ ] **Step 8: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_note_draft_automation.py tests/test_run291_private_draft_audit.py tests/test_run292_note_rendered_body_audit.py tests/test_run417_note_content_verification.py -q`

Expected: PASS.

- [ ] **Step 9: Run static privacy and mutation-surface guards**

Confirm no new raw DOM/body/URL logging/artifact output and no new public-release action. Confirm read-only audit still has no mutation methods.

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add note_draft_automation.py tests/test_note_draft_automation.py note_document_contract.py note_document_dom.py run292_note_rendered_body_audit.py tests/test_run292_note_rendered_body_audit.py <effective-run417-files>
git commit -m "fix: require canonical note persistence verification"
```

---

### Task 6: Falsification, Full Regression, and P0-A Closure Evidence

**Files:**
- Test-only changes if a missing falsification case is discovered.
- No feature expansion.

**Interfaces:**
- Consumes: effective Task 5 production path.
- Produces: auditable evidence for P0-A closure; P0 overall remains NO-GO until other blockers close.

- [ ] **Step 1: Re-run the original C23 semantic-corruption probes against the effective verifier**

At minimum replay changes equivalent to:
- negation flip
- `10` -> `99`
- seconds -> years
- Product A -> another entity
- comparison target change.

Expected: every mutation rejects deterministically.

- [ ] **Step 2: Run all new P0-A tests**

Run: `python -m pytest tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_run291_private_draft_audit.py tests/test_run292_note_rendered_body_audit.py tests/test_run293_private_draft_guard_diagnostics.py tests/test_run294_note_eyecatch_persistence_diagnostics.py tests/test_run295_note_eyecatch_persistence.py tests/test_note_draft_automation.py tests/test_run417_note_content_verification.py -q`

Expected: 0 failures.

- [ ] **Step 3: Run repository regression suite without firing external workflows or model APIs**

Run the repository's current canonical local test command for `tests/` plus existing synthetic-production/security guards used on latest main.

Expected: 0 failures; record exact pass/skip counts rather than summarizing them vaguely.

- [ ] **Step 4: Run workflow/static validation**

Validate changed YAML and source-inspection tests. Confirm the private-draft audit emits only content-free canonical metrics and P0-C public containment remains intact.

Expected: PASS.

- [ ] **Step 5: Compare branch to its rebased/latest main base**

Expected changed files are limited to the P0-A design/plan, canonical document modules/tests, read-only audit integration, production note verifier integration, and narrowly necessary workflow/test files. Any unrelated Daily/Fresh/Rolling/model-routing diff is a STOP condition.

- [ ] **Step 6: Produce closure report with exact scope**

Report separately:
- A-2a offline canonical renderer contract: GO/NO-GO
- A-1 real saved/reopened note DOM contract: GO/NO-GO
- P0-A C23 lossless verification: GO/NO-GO
- N01/B/C remaining blockers: unchanged
- P0 overall: still NO-GO unless separately proven later.

- [ ] **Step 7: Request code review / whole-branch review before merge**

Use Superpowers `requesting-code-review` (or the strongest available fresh review path in the current Chat environment) against the entire diff and the original spec. Resolve substantive findings with `receiving-code-review` discipline.

- [ ] **Step 8: Run `verification-before-completion` checks after the final review fixes**

Re-run the exact focused and repository regression commands after the last code change. Do not rely on earlier green runs.

- [ ] **Step 9: Create PR; do not auto-merge**

PR must name the real-DOM evidence used, normalization codes, exact test results, and explicitly state that N01 durable idempotency remains unresolved.

- [ ] **Step 10: Commit any final test-only corrections before PR**

```bash
git add <only-p0-a-files>
git commit -m "test: verify P0-A lossless note delivery contract"
```

---

## Execution Order and Stop Gates

1. Tasks 1-3 are safe offline/read-only implementation and may proceed without changing production acceptance.
2. Task 4 is a hard external-evidence gate. A real current private draft must pass complete supported mapping; otherwise stop and refine only the evidence-backed mapping.
3. Task 5 is forbidden until Task 4 is green.
4. Task 6 may call P0-A closed only if both the real saved/reopened DOM proof and effective production-path falsification are green.
5. Even after P0-A closure, P0 overall remains NO-GO while B-1/B-2/B-3/B-4/C-1/C-2 and N01-related work remain unresolved.

## Native Chat Execution Method

The user has selected Chat-centered execution. After this plan is approved, implement it in this Chat with `superpowers:executing-plans`, using TDD task-by-task. Use GitHub writes only on the isolated P0-A branch; do not merge without an explicit merge decision after final verification and review.
