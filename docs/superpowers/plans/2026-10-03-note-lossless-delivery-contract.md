# P0-A Note Lossless Delivery Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace heuristic note-body integrity checks with a deterministic, model-free canonical document contract that proves the approved note presentation survives renderer, note save, and reopen without semantic or structural corruption.

**Architecture:** Build a pure-Python canonical document layer first. Then attach a thin read-only DOM adapter to the existing Run291/292 private-draft audit. Only after one real saved private draft proves the DOM mapping and every legitimate note normalization is frozen by evidence-backed fixtures will the production path in `note_draft_automation.py` switch from coarse text heuristics to mandatory canonical equality.

**Tech Stack:** Python 3.11, stdlib `dataclasses` / `html.parser` / `unicodedata`, existing Playwright note automation/audit, Pytest-compatible tests, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-03-note-lossless-delivery-contract-design.md`

## Global Constraints

- Baseline: `13454791d35a06a0bc1c7dfbe99478e9ebb7176f`; recheck latest `main` before implementation.
- Expected content comes only from the current Publication Contract manuscript after approved deterministic Run222 presentation transforms.
- Actual note DOM never defines or widens expected content.
- Zero model calls for integrity verification.
- Unsupported Markdown or note DOM fails closed; no silent plain-text flattening.
- Numbers, negation, units, entities, comparison targets, URLs, code, list order/numbering, headings, quotes, dividers, and authored line breaks are contract material.
- No public-release automation change.
- No raw unpublished manuscript, DOM, draft URL, screenshot, storage state, cookie, image URL, or arbitrary exception text in public logs/summaries/annotations/artifacts.
- Existing Evidence / Fact / Human Appeal / Publication / current-contract / image-proof / exact-sync-id / current-run causality gates remain unchanged.
- N01 durable idempotency is out of scope.
- Tasks 1-4 do not change production acceptance. Task 5 starts only after the real-DOM evidence gate passes.
- No new runtime dependency unless separately reviewed.

## Review Focus

1. Markdown metacharacters inside code, links, and literal text must not be reinterpreted.
2. Nested/mixed lists or continuation lines must be preserved explicitly or rejected, never flattened.
3. Unicode normalization is narrow: NFC for ordinary prose only; no broad full-/half-width or lookalike normalization.
4. note wrapper churn must fail safely without content disclosure; only evidence-backed wrappers may become transparent.
5. A body that matches immediately after paste but changes after reopen must fail and must not advance the queue.

---

## File Map

**Create**
- `note_document_contract.py` — canonical nodes, Markdown parser, safe-HTML renderer/parser, normalization, comparator, safe mismatch receipt.
- `note_document_dom.py` — read-only note DOM snapshot adapter and explicit note DOM mapping policy.
- `tests/test_note_document_contract.py`
- `tests/test_note_document_dom.py`

**Modify**
- `run292_note_rendered_body_audit.py`
- `tests/test_run292_note_rendered_body_audit.py`
- `.github/workflows/note-private-draft-audit.yml` only if new test invocation / safe metrics require it.
- `note_draft_automation.py` only in Task 5 after evidence gate.
- `tests/test_note_draft_automation.py` only in Task 5 after evidence gate.
- `run194_note_persistent_cloud.py` only if composition wiring is actually necessary; current file composes `note_draft_automation.py` through `cloud.base` and should otherwise stay unchanged.
- `run222_note_presentation_integrity.py` only if a RED test proves the approved presentation transform violates the canonical contract.

There is no current `run417` source/test file on `main`; do not invent one. The production acceptance boundary for this plan is the real `note_draft_automation.py` create/save/reopen path, composed by `run194_note_persistent_cloud.py`.

---

### Task 1: Canonical Model, Markdown Parser, and Comparator

**Files:**
- Create: `note_document_contract.py`
- Create: `tests/test_note_document_contract.py`

**Interfaces:**
- `CONTRACT_VERSION: str`
- `NORMALIZATION_POLICY_VERSION: str`
- `CanonicalContractError(Exception)` with fixed `code: str`
- immutable node types: `Document`, `Heading`, `Paragraph`, `OrderedList`, `UnorderedList`, `ListItem`, `CodeBlock`, `InlineCode`, `Link`, `Strong`, `Emphasis`, `BlockQuote`, `Divider`, `Text`, `HardBreak`
- `parse_presentation_markdown(markdown_text: str) -> Document`
- `normalize_document(document: Document, *, normalization_codes: tuple[str, ...] = ()) -> Document`
- `compare_documents(expected: Document, actual: Document) -> dict[str, object]`

- [ ] **Step 1: Write RED positive parser tests**

Cover H2-H4, paragraphs, the currently supported authored line-break form, unordered list, ordered list including non-1 start, blockquote, divider, fenced code, inline code, strong, emphasis, exact HTTP/HTTPS links, Japanese text, emoji, and NFC-equivalent prose.

- [ ] **Step 2: Run and confirm RED**

`python -m pytest tests/test_note_document_contract.py -q`

Expected: FAIL because module/interfaces do not exist.

- [ ] **Step 3: Implement the minimal canonical node model and parser**

Unsupported/ambiguous Markdown raises `CanonicalContractError(code="unsupported_markdown")`. Do not silently reinterpret nested/mixed list syntax or unsupported constructs as prose.

- [ ] **Step 4: Write RED adversarial comparison tests**

Required mutations: negation flip; number; unit; entity/product; comparison target; href; item reorder/add/delete; ordered-list start; heading level; paragraph add/delete/duplicate; code character and code whitespace; inline-code flattening; quote flattening; unexpected H1; literal known internal control marker such as `[ARTICLE]`/`【ARTICLE】` where existing AIIF marker policy treats it as internal; unsupported Markdown; unsupported mixed/nested list form.

- [ ] **Step 5: Run and confirm comparator RED**

`python -m pytest tests/test_note_document_contract.py -q`

- [ ] **Step 6: Implement narrow normalization and content-free comparison receipt**

Only source newline normalization and NFC for ordinary prose are allowed offline initially. Do not normalize code whitespace, URLs, punctuation, list numbering, or full-/half-width differences.

`compare_documents()` returns categories/paths/versions only; never raw text or URLs.

- [ ] **Step 7: Run Task 1 GREEN**

`python -m pytest tests/test_note_document_contract.py -q`

Expected: all tests PASS, zero network/model access.

- [ ] **Step 8: Commit**

```bash
git add note_document_contract.py tests/test_note_document_contract.py
git commit -m "feat: add canonical note document contract"
```

---

### Task 2: Canonical Safe-HTML Projection and Offline Round Trip

**Files:**
- Modify: `note_document_contract.py`
- Modify: `tests/test_note_document_contract.py`
- Read-only comparison: `note_draft_automation.py::_markdown_to_safe_html`

**Interfaces:**
- `render_safe_html(document: Document) -> str`
- `parse_safe_html(html_text: str) -> Document`

- [ ] **Step 1: Write RED round-trip tests**

For every supported node require:
`parse_safe_html(render_safe_html(doc)) == normalize_document(doc)`.

Include metacharacters inside code/link text, code blank lines/indentation/trailing-space cases, non-1 ordered-list start, authored line break, and Unicode cases.

- [ ] **Step 2: Run and confirm RED**

`python -m pytest tests/test_note_document_contract.py -q`

- [ ] **Step 3: Implement HTML projection from canonical nodes**

No regex rescanning of Markdown. Escape text/attributes deterministically. Only HTTP/HTTPS links are supported.

- [ ] **Step 4: Implement strict safe-HTML parser**

Unknown semantic tag or ambiguous nesting => `unsupported_safe_html`.

- [ ] **Step 5: Add legacy-renderer compatibility tests without switching production**

For representative current AIIF presentation fixtures, render with both current `_markdown_to_safe_html()` and the new renderer, parse both outputs canonically, and require equality. If a semantic difference appears, classify it as an existing renderer defect or unsupported source; do not change production in this task.

- [ ] **Step 6: Verify GREEN and no production diff**

```bash
python -m pytest tests/test_note_document_contract.py tests/test_note_draft_automation.py -q
git diff -- note_draft_automation.py run222_note_presentation_integrity.py
```

Expected: tests PASS; production diff empty.

- [ ] **Step 7: Commit**

```bash
git add note_document_contract.py tests/test_note_document_contract.py
git commit -m "test: prove canonical safe html round trip"
```

---

### Task 3: Read-Only note DOM Adapter and Run292 Canonical Audit

**Files:**
- Create: `note_document_dom.py`
- Create: `tests/test_note_document_dom.py`
- Modify: `run292_note_rendered_body_audit.py`
- Modify: `tests/test_run292_note_rendered_body_audit.py`
- Modify if required: `.github/workflows/note-private-draft-audit.yml`

**Interfaces:**
- `snapshot_note_body(body_locator: object) -> dict[str, object]`
- `document_from_note_snapshot(snapshot: dict[str, object], *, allowed_normalizations: tuple[str, ...] = ()) -> Document`
- Run292 safe receipt includes only canonical match, node counts, unsupported counts, normalization codes, mismatch category/path, contract/policy versions, and existing read-only flags.

- [ ] **Step 1: Write RED synthetic DOM tests**

Cover headings, paragraphs, ordered/unordered lists, list start/order, links/href, strong/emphasis, inline code, fenced code, quote, divider, authored break, wrapper-only containers, unknown tag, missing href, and semantic mutations.

- [ ] **Step 2: Write RED privacy/mutation-surface tests**

The adapter/audit must contain no click/fill/keyboard/paste/save/screenshot/Notion PATCH/public-release surface. Mismatch results must not expose actual/expected text, manuscript, raw DOM, href, title, or draft URL.

- [ ] **Step 3: Run and confirm RED**

`python -m pytest tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py -q`

- [ ] **Step 4: Implement one read-only browser `evaluate()` snapshot and strict initial mapping**

The transient snapshot may contain content needed for in-memory comparison but is never printed, persisted, or returned publicly. No speculative note-specific normalization: unknown structures fail `unsupported_note_dom`.

- [ ] **Step 5: Make canonical equality mandatory for Run292 read-only audit**

Visible-text metrics may remain secondary diagnostics; they cannot override canonical mismatch/unsupported DOM.

- [ ] **Step 6: Run Run291-295 regression GREEN**

```bash
python -m pytest \
  tests/test_note_document_dom.py \
  tests/test_run291_private_draft_audit.py \
  tests/test_run292_note_rendered_body_audit.py \
  tests/test_run293_private_draft_guard_diagnostics.py \
  tests/test_run294_note_eyecatch_persistence_diagnostics.py \
  tests/test_run295_note_eyecatch_persistence.py -q
```

Expected: PASS; unit tests make no browser/network/model call.

- [ ] **Step 7: Verify workflow privacy/read-only contract**

Static tests must still prove no draft creation/publication/mutation and no raw body/DOM/draft URL/image URL output.

- [ ] **Step 8: Commit**

```bash
git add note_document_dom.py tests/test_note_document_dom.py run292_note_rendered_body_audit.py tests/test_run292_note_rendered_body_audit.py .github/workflows/note-private-draft-audit.yml
git commit -m "feat: add read-only canonical note DOM audit"
```

---

### Task 4: Real Private-Draft Evidence Gate and Frozen Normalization Policy

**Precondition:** Tasks 1-3 GREEN. Production acceptance remains unchanged.

**Files:**
- Modify only evidence-backed mapping/normalization in `note_document_contract.py` / `note_document_dom.py` and their tests.
- Update design evidence notes only if observed note behavior requires it.

- [ ] **Step 1: Select one exact existing Ready / 投稿準備中 private draft with no public-post evidence using existing Run291 preflight**

Expected: `audit_ready`, `read_only=true`, `zero_gemini_calls=true`, `draft_mutation=false`.

- [ ] **Step 2: Execute only the existing private-draft audit read-only**

No Daily/Fresh/Rolling, model call, note write, Notion write, screenshot artifact, or public release.

Expected: either complete supported canonical mapping, or fail-closed content-free unsupported/mismatch category.

- [ ] **Step 3: For every legitimate unsupported note structure, write a RED fixture before adding a rule**

Each note-specific rule gets a fixed normalization code and must prove a nearby semantic mutation still fails. Never add a catch-all whitespace/wrapper rule just to make the draft pass.

- [ ] **Step 4: Implement the minimum evidence-backed rule and rerun offline tests**

`python -m pytest tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py -q`

- [ ] **Step 5: Re-run the real read-only audit**

Task 5 GO requires all:
- `canonical_match=true`
- unsupported expected/actual node counts = 0
- every applied note normalization has committed fixture + rationale
- no unpublished content in public logs/summary/artifacts.

If any condition fails, **STOP; Task 5 is NO-GO**.

- [ ] **Step 6: Commit frozen evidence-backed policy**

```bash
git add note_document_contract.py note_document_dom.py tests/test_note_document_contract.py tests/test_note_document_dom.py tests/test_run292_note_rendered_body_audit.py docs/superpowers/specs/2026-10-03-note-lossless-delivery-contract-design.md
git commit -m "test: freeze evidence backed note normalization policy"
```

---

### Task 5: Production Create / Save / Reopen Canonical Gate

**Hard precondition:** Task 4 exit criteria are green.

**Files:**
- Modify: `note_draft_automation.py`
- Modify: `tests/test_note_draft_automation.py`
- Read/verify composition: `run194_note_persistent_cloud.py`
- Modify `run194_note_persistent_cloud.py` only if wiring is actually required after tests prove current composition cannot reach the new verifier.

**Interfaces:**
- Production uses `parse_presentation_markdown()`, `render_safe_html()`, `snapshot_note_body()`, `document_from_note_snapshot()`, `compare_documents()`.

- [ ] **Step 1: Write RED production corruption tests at both boundaries**

Mock the body after initial paste and separately after reopen. Mutate number, negation, unit, entity, href, list order/start, heading level, inline code, and code whitespace. Require `NoteDraftError` and prove queue advancement is not reached.

- [ ] **Step 2: Write RED unsupported-source / unsupported-DOM tests**

Unsupported approved presentation or unsupported readback DOM must block before queue success.

- [ ] **Step 3: Write RED save/reopen divergence test**

Post-paste canonical match=true; reopened body differs by one semantic value. Reopen verification must fail and `_mark_draft_created()` must not run.

- [ ] **Step 4: Run and confirm RED**

`python -m pytest tests/test_note_draft_automation.py -q`

- [ ] **Step 5: Route `_markdown_to_safe_html()` through the canonical parser/renderer while preserving its public signature**

Run222 remains upstream and unchanged unless separately proven defective. Unsupported syntax is mapped to a fixed `NoteDraftError`, not raw exception text.

- [ ] **Step 6: Replace `_verify_body_content()` acceptance with canonical DOM equality**

Use the same mandatory canonical gate immediately after paste and after reopen in `_save_draft_and_verify()`. Coarse visible metrics may remain diagnostic-only and can never override canonical mismatch.

- [ ] **Step 7: Verify queue ordering remains unchanged**

`_mark_draft_created()` occurs only after `_create_browser_draft()` returns from successful save/reopen canonical verification. Do not attempt N01 idempotency work here.

- [ ] **Step 8: Run focused GREEN**

```bash
python -m pytest \
  tests/test_note_document_contract.py \
  tests/test_note_document_dom.py \
  tests/test_note_draft_automation.py \
  tests/test_run291_private_draft_audit.py \
  tests/test_run292_note_rendered_body_audit.py -q
```

- [ ] **Step 9: Run privacy/source-inspection guards**

No new raw body/DOM/URL logging, no screenshot upload path, no public release, and read-only audit still contains no mutation surface.

- [ ] **Step 10: Commit**

```bash
git add note_draft_automation.py tests/test_note_draft_automation.py note_document_contract.py note_document_dom.py run292_note_rendered_body_audit.py tests/test_run292_note_rendered_body_audit.py
git commit -m "fix: require canonical note persistence verification"
```

---

### Task 6: Falsification, Full Regression, Review, and PR

**Files:** Test-only corrections if a missing falsification case is found. No feature expansion.

- [ ] **Step 1: Replay original C23 semantic-corruption probes against the effective production verifier**

At minimum: negation flip, `10 -> 99`, seconds -> years, Product A -> other entity, comparison-target change. Every mutation must reject deterministically.

- [ ] **Step 2: Run all P0-A focused tests**

```bash
python -m pytest \
  tests/test_note_document_contract.py \
  tests/test_note_document_dom.py \
  tests/test_run291_private_draft_audit.py \
  tests/test_run292_note_rendered_body_audit.py \
  tests/test_run293_private_draft_guard_diagnostics.py \
  tests/test_run294_note_eyecatch_persistence_diagnostics.py \
  tests/test_run295_note_eyecatch_persistence.py \
  tests/test_note_draft_automation.py -q
```

Expected: 0 failures.

- [ ] **Step 3: Run current repository canonical local regression + existing synthetic/security guards without firing workflows or model APIs**

Record exact pass/fail/skip counts.

- [ ] **Step 4: Validate changed workflow YAML/static contracts**

P0-C containment must remain intact.

- [ ] **Step 5: Compare branch to latest main**

Only P0-A docs/modules/tests/read-only audit/production verifier files are allowed. Unrelated Daily/Fresh/Rolling/model-routing diff => STOP.

- [ ] **Step 6: Produce scope-separated closure report**

Report A-2a, A-1, and P0-A/C23 independently as GO/NO-GO. Keep N01/B/C blockers unchanged. P0 overall remains NO-GO unless separately proven later.

- [ ] **Step 7: Use Superpowers `requesting-code-review` for whole-branch review**

Resolve substantive review findings with `receiving-code-review` discipline.

- [ ] **Step 8: Use `verification-before-completion` after the final code change**

Re-run focused and repository regression commands after the final fix; earlier green runs do not count.

- [ ] **Step 9: Create PR; do not auto-merge**

PR must include real-DOM evidence, normalization codes, exact test counts, and explicit statement that N01 remains unresolved.

---

## Stop Gates

1. Tasks 1-3: offline/read-only implementation only; production acceptance unchanged.
2. Task 4: hard real-environment evidence gate.
3. Task 5: forbidden unless Task 4 is fully green.
4. Task 6 may call P0-A closed only when real saved/reopened DOM proof and effective production-path falsification are both green.
5. P0 overall remains NO-GO while B-1/B-2/B-3/B-4/C-1/C-2/N01-related work remains unresolved.

## Execution Method

The user selected Chat-centered execution. After plan approval, execute in this Chat with `superpowers:executing-plans`, task-by-task and RED-first, on the isolated P0-A branch. Do not merge without an explicit merge decision after final review and verification.
