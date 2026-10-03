# P0-A Note Lossless Delivery Contract Design

Status: design approved in chat; implementation not yet authorized by this document alone  
Date: 2026-10-03  
Repository: `trendhub-ab/ai-intelligence-factory`  
Design baseline: `13454791d35a06a0bc1c7dfbe99478e9ebb7176f`  
Audit baseline ancestor: `a26eea5e0be5d4252b19fd535d2b664cc02e9e86`

## 1. Purpose

Close P0-A without weakening publication quality or relying on probabilistic semantic checks.

The system must be able to prove that the approved AIIF manuscript delivered through note's web editor preserves the intended visible content and editorial structure after note accepts, saves, and reopens the draft.

This design separates two contracts that were previously conflated:

1. **A-2a — AIIF manuscript -> deterministic safe HTML / expected document**
2. **A-1 — note accepted DOM/readback -> actual document**

A-2a is closed offline. A-1 is closed only with read-only evidence from an existing private note draft. Production acceptance changes only after both contracts are demonstrated.

## 2. Evidence and current implementation

At the design baseline, the effective note path is:

`current Publication Contract manuscript`
-> `Run222 presentation-only transform`
-> `note_draft_automation._markdown_to_safe_html()`
-> browser paste event
-> insertion verification
-> draft save
-> reopen stable edit URL
-> persisted title/body verification
-> queue transition.

Relevant files include:

- `note_draft_automation.py`
- `run194_note_persistent_cloud.py`
- `run222_note_presentation_integrity.py`
- `run291_note_private_draft_audit.py`
- `run292_note_rendered_body_audit.py`
- `run295_note_private_draft_audit.py`
- `.github/workflows/note-private-draft-audit.yml`
- related note draft and audit tests.

`note_draft_automation._verify_body_content()` currently proves only a coarse visible insertion condition. The post-save path reuses that class of check after reopening. This is useful as a smoke check but is not a lossless delivery contract.

Run292 already demonstrates an important design direction: derive expected visible content from the same safe HTML renderer used by draft creation rather than from the legacy plain-text helper. However, diagnostics such as `exact_visible_match` are not currently the production acceptance boundary.

The repository also already provides a read-only private-draft audit path. It requires an exact current Ready / 投稿準備中 target, opens an existing private edit route, performs zero model calls, and does not create, edit, save, publish, or withdraw a note.

The latest main change from the audit baseline is PR #714, P0-C public-containment work. It changes diagnostic/output handling and does not redefine the note manuscript renderer or the Run291/292 body-equivalence logic. P0-A must preserve those new containment constraints.

## 3. Root cause

The root cause is not simply that the verifier uses too few anchors.

The root cause is the absence of a single, explicit, deterministic contract that answers all three questions below:

1. What exact editorial document is expected after AIIF's intentional note-presentation transforms?
2. Which transformations performed by the renderer and note editor are semantically acceptable normalizations?
3. How is the reopened note DOM converted into an independently derived representation that can be compared with the expected document?

Without that contract, adding more anchors or wider length windows still permits changes outside checked regions. A verifier can also accidentally normalize away evidence of corruption.

## 4. Non-negotiable invariants

1. **Approved source is authoritative.** Expected content is derived only from the already-approved current Publication Contract manuscript plus explicitly allowed deterministic presentation transforms.
2. **Actual never defines expected.** The note DOM/readback must never be used to construct or mutate the expected representation.
3. **No LLM equivalence judge.** Gemini/OpenAI/other model calls are not part of the integrity decision.
4. **Fail closed on unsupported syntax.** Unknown manuscript constructs or unknown note DOM constructs cannot silently degrade into plain text and PASS.
5. **Semantic values are exact.** Numbers, negation, units, product names, comparison targets, URLs, code, and ordered content must not change.
6. **Structure matters.** Heading levels, list type/order, link destination, code block boundaries, quote boundaries, and divider placement are part of the contract where used by AIIF.
7. **Private draft only.** This design does not introduce public-release automation.
8. **Zero disclosure regression.** P0-A diagnostics must not reintroduce raw unpublished manuscripts, draft URLs, screenshots, browser storage state, or raw private DOM into public Actions output/artifacts.
9. **No gate weakening.** Evidence, Fact, Human Appeal, Publication, and current-publication-contract requirements remain unchanged.
10. **No API-cost increase.** Integrity proof is deterministic and model-free.

## 5. Canonical Document Model

Introduce one small, isolated module, provisionally `note_document_contract.py`, whose job is only document representation, normalization, extraction, and comparison.

The canonical model is an ordered tree. Initial node set:

- `Document`
- `Heading(level, children)`
- `Paragraph(children)`
- `OrderedList(start, items)`
- `UnorderedList(items)`
- `ListItem(children)`
- `CodeBlock(language, text)`
- `InlineCode(text)`
- `Link(href, children)`
- `Strong(children)`
- `Emphasis(children)`
- `BlockQuote(children)`
- `Divider`
- `Text(value)`
- `HardBreak`

The node set is intentionally narrow. It covers AIIF's currently supported editorial Markdown surface. Unsupported constructs must return an explicit unsupported-syntax result rather than being guessed.

### 5.1 Expected representation

Expected canonical document is built in this order:

1. Read byte-valid current Publication Contract manuscript.
2. Apply current approved presentation-only transforms (`Run222`) to produce the note-editor manuscript.
3. Parse that manuscript into the canonical document model.
4. Render safe HTML from the same canonical model, not from an independent regex-only interpretation.
5. Optionally reparse the generated safe HTML in offline tests and require canonical equality.

This makes the parser/model the single semantic authority and the HTML renderer a projection of that authority.

### 5.2 Actual representation

Actual canonical document is independently built from the reopened note editor body DOM.

The extractor maps allowed note DOM structures to canonical nodes. Wrapper elements that carry no editorial meaning may be ignored only when explicitly allow-listed.

The extractor must reject or classify as unsupported any DOM structure that cannot be mapped without ambiguity.

## 6. Lossless equivalence

PASS requires equality of the normalized expected and actual canonical documents.

Examples that must BLOCK:

- `10` -> `99`
- `秒` -> `年`
- an affirmative statement -> a negated statement, or the reverse
- Product A -> Product B
- comparison target A -> target B
- link label unchanged but `href` changed
- ordered list item order changed
- ordered list start number changed
- unordered list item removed, added, or reordered
- heading level changed
- paragraph removed or duplicated
- code text or code whitespace changed
- inline code converted into ordinary prose when the source uses inline code
- quote content moved into ordinary paragraph text
- divider removed when it is part of the approved presentation structure
- internal markers such as `ARTICLE` introduced into visible body
- unexpected visible body-level H1 after the title-field transform

The contract must not attempt to infer that two different values are 'close enough'.

## 7. Normalization allowlist

Normalization is minimal and versioned. Only transformations supported by evidence may be allowed.

Initial offline-safe normalization candidates:

- CRLF / CR -> LF before parsing source manuscript
- HTML entity decoding as part of HTML/DOM parsing
- Unicode canonical normalization for ordinary prose text, using one fixed form consistently on expected and actual sides
- removal of non-semantic DOM wrappers proven not to alter text or editorial structure
- browser visual line wrapping that does not create an authored `HardBreak`

The following are **not** automatically normalized away:

- arbitrary whitespace inside code
- ordered-list numbering
- URL changes
- punctuation changes that alter the actual text
- paragraph/list/heading boundary changes
- full-width/half-width conversions unless separately proven and explicitly approved
- character substitutions that merely look similar
- note-specific empty blocks until observed and classified in read-only evidence.

Every note-specific normalization must have:

1. a named normalization code,
2. a regression fixture,
3. read-only real-DOM evidence,
4. an explicit rationale showing why semantics and intended presentation are preserved.

No catch-all normalization is allowed.

## 8. Markdown and renderer contract

The current regex renderer recognizes a limited Markdown subset. P0-A must turn that implicit subset into an explicit contract.

For each supported construct, tests must prove:

`source markdown -> canonical expected -> safe HTML -> reparsed canonical == canonical expected`.

At minimum cover:

- H2-H4 headings
- ordinary paragraphs
- authored hard line breaks represented by the supported source form
- unordered lists
- ordered lists including non-1 starts if the source grammar admits them
- blockquotes
- horizontal dividers
- fenced code blocks, language metadata, blank lines, indentation, and trailing spaces where semantically relevant
- inline code
- strong emphasis
- emphasis
- HTTP/HTTPS links with exact destinations
- Japanese text, ASCII, symbols, emoji, and Unicode normalization cases.

If the existing renderer cannot represent a supported source construct losslessly, implementation must either fix the renderer or explicitly reject that construct before note delivery. It must not flatten it silently.

## 9. Read-only real-DOM proof protocol

Extend the existing Run291/292/295 private-draft audit family rather than create a second browser-audit subsystem.

The proof protocol:

1. Exact `sync_id` identifies one existing private draft in current Ready / 投稿準備中 state.
2. Reconstruct the approved presentation manuscript from Content Intelligence using the current contract.
3. Build expected canonical document before opening the note draft.
4. Open only an existing note edit route discovered through the existing private-draft audit mechanism.
5. Read the persisted body DOM without click/fill/paste/save/publish actions.
6. Build actual canonical document from DOM.
7. Compare expected vs actual inside the private runner.
8. Emit only non-content metrics and categorical mismatch codes.

Allowed external diagnostics include:

- `canonical_match: true|false`
- expected/actual node counts by node class
- `unsupported_expected_node_count`
- `unsupported_actual_node_count`
- normalization codes applied
- mismatch category such as `text_value_mismatch`, `link_href_mismatch`, `list_order_mismatch`, `code_mismatch`, `structure_mismatch`
- first mismatching node path hashed or index-only, never raw node text
- current contract version / normalization policy version
- zero-model / read-only / mutation=false / public-release=false flags.

Forbidden output includes unpublished title/body text, expected or actual raw DOM, draft URL, screenshot, storage state, cookies, image URL, or arbitrary exception payloads.

## 10. TDD requirements

Implementation starts only after an implementation plan is approved. When it starts, tests are written RED first.

### 10.1 Adversarial equality tests

Required negative fixtures include at least:

- negation flip
- number change
- unit change
- product/entity change
- comparison-target change
- link destination change
- item reorder
- item deletion/addition
- heading-level change
- paragraph duplication/deletion
- code character change
- code indentation/whitespace change
- inline-code flattening
- quote flattening
- unexpected H1
- internal marker injection
- unsupported Markdown construct
- unsupported note DOM construct.

All must fail closed.

### 10.2 Positive fixtures

Required positive fixtures include:

- current AIIF-style Japanese article structure
- headings + prose + links + emphasis
- ordered and unordered lists
- fenced code + inline code
- Sources/Evidence + disclaimer + CTA order
- Unicode text and symbols
- explicitly allow-listed note normalization fixtures.

### 10.3 Privacy tests

Source inspection/regression tests must prove the audit code does not call mutation surfaces such as click/fill/paste/save/queue-patch/public-release actions and does not print raw content.

## 11. Rollout phases

### Phase 0 — design only

No production behavior change. This document is the output.

### Phase 1 — offline canonical contract

Add canonical model/parser/renderer/comparator and RED->GREEN unit/adversarial tests. Do not change production note acceptance yet.

Exit criteria:

- all offline adversarial mutations reject,
- supported source fixtures round-trip through safe HTML canonically,
- unsupported syntax fails closed,
- zero model/API calls.

### Phase 2 — read-only private-draft audit

Add canonical DOM extraction to the existing private-draft audit path. No new draft is created and no existing draft is mutated.

Exit criteria:

- at least one real current private draft produces a complete supported DOM mapping,
- note-specific normalizations are observed and documented,
- no unpublished content is emitted outside the private comparison process.

If real DOM contains unsupported structures, production remains unchanged and the design returns to Phase 1/2 for explicit mapping.

### Phase 3 — freeze normalization policy

Convert observed legitimate note transformations into named, narrow normalization rules with fixtures.

Exit criteria:

- each normalization has evidence and tests,
- no broad text normalization can hide number/entity/unit/URL/code changes.

### Phase 4 — production verifier integration

Only after Phase 1-3 evidence, replace the coarse body-acceptance boundary used by the creation/save/reopen path with canonical comparison.

The old coarse verifier may remain temporarily as a secondary diagnostic, but it cannot override a canonical mismatch.

Canonical mismatch or unsupported actual DOM => draft delivery attempt fails closed and the queue must not advance as successfully delivered.

N01 durable idempotency remains a separate P0 workstream. P0-A must not claim that a canonical PASS alone makes the create/queue transaction idempotent.

### Phase 5 — independent verification

Re-run the original semantic-corruption probes plus expanded adversarial fixtures against the effective production path. Confirm no weakening of current Publication Contract, image proof, private-draft-only policy, or P0-C output containment.

## 12. Provisional file boundary

Expected implementation touch set, to be refined by the implementation plan:

New:

- `note_document_contract.py`
- `tests/test_note_document_contract.py`
- adversarial contract tests if kept separate.

Likely modified:

- `note_draft_automation.py` — renderer/prod verification integration only after evidence gate
- `run292_note_rendered_body_audit.py` or a narrow successor/wrapper — expected/actual canonical comparison
- corresponding Run291/292/295 tests
- `.github/workflows/note-private-draft-audit.yml` — only safe metric names/test invocation if needed.

Potentially modified only if evidence requires it:

- `run222_note_presentation_integrity.py`.

No unrelated Daily/Fresh/Rolling Re-review logic is in scope.

## 13. Rollback and compatibility

During Phase 1-3, production delivery behavior is unchanged, so rollback is simply removal/revert of offline/read-only additions.

For Phase 4:

- keep the previous verifier code path available behind an emergency diagnostic-only flag for one release window if operationally useful;
- the flag must never permit a canonical mismatch to PASS;
- rollback means reverting the production integration commit, not weakening the comparator at runtime;
- queue/draft records created before the contract version are not rewritten automatically.

The canonical contract and normalization policy must expose version identifiers so audit results can be tied to the exact rules used.

## 14. Security and privacy interaction with P0-C

P0-A must inherit the P0-C containment posture merged in PR #714.

No raw manuscript/DOM/screenshot is uploaded as a GitHub Actions artifact. No private body is printed to logs or step summaries. Exceptions crossing the private comparison boundary are mapped to fixed categorical codes.

Debugging value is preserved through counts, categories, policy versions, and content-free structural diagnostics.

## 15. Acceptance criteria for closing P0-A

P0-A is not closed merely because unit tests pass.

Closure requires all of the following:

1. Offline canonical source/renderer contract passes all supported positive fixtures.
2. Required semantic adversarial mutations are rejected deterministically.
3. Unsupported source syntax fails closed.
4. Existing private note draft is audited read-only using actual saved/reopened note DOM.
5. Every note-specific normalization used for PASS is evidence-backed and regression-tested.
6. Production create/save/reopen acceptance uses canonical equality as the mandatory gate.
7. A canonical mismatch cannot be overridden by anchor, length, or heading-count heuristics.
8. Queue success cannot be recorded solely on a coarse body check.
9. No model call is required for integrity verification.
10. No P0-C information-boundary regression occurs.
11. Independent verification re-runs the semantic mutation probes against the effective path and observes rejection.

## 16. Explicit non-goals

This work does not:

- solve N01 durable draft idempotency,
- solve C01 pre-delivery recovery policy,
- change Gemini routing,
- change Fresh validation,
- change Rolling Re-review,
- automate public note publication,
- relax any Evidence/Fact/Human/Publication gate,
- redesign article prose or paid-member UX,
- infer unsupported note behavior without read-only evidence.

Those remain separate workstreams and must not be bundled into P0-A merely because they touch note delivery.

## 17. Decision

Adopt the two-stage Canonical Document Contract:

`approved presentation manuscript -> expected canonical document`

and independently:

`reopened note DOM -> actual canonical document`

Production note delivery may advance only when the versioned, narrowly normalized canonical documents are equal and all existing publication/delivery prerequisites also pass.

This is the selected design because it closes the demonstrated semantic-verification gap deterministically, uses zero model calls, preserves the private-draft boundary, and lets AIIF prove each external note-editor normalization before trusting it.
