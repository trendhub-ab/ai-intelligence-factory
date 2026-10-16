# V1 Eyecatch Fallback Contract Implementation Plan

**Goal:** Guarantee that a valid long public headline still produces an exact, non-truncated 1280x670 deterministic eyecatch when the Gemini layout optimizer is unavailable or rejects its plan.

**Architecture:** Keep Run178's current one-call optional layout optimization and fail closed on model rewrites. Repair only the deterministic fallback so it can lay out the complete canonical public title. Do not change provider routing, quality thresholds, Ready policy, Notion semantics, or V2.

**Tech stack:** Python, Pillow, unittest/pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-v1-v2-runtime-failure-architecture-audit.md`

**Global constraints:** exact headline preservation; no ellipsis; 1280x670; zero extra provider calls; main untouched; minimal diff.

## Task 1 — RED: reproduce long-title fallback failure

**Files:**
- Modify: `tests/test_run178_eyecatch_editorial_layout_optimizer.py`
- Production under test: `editorial_eyecatch.py`, `run178_eyecatch_editorial_layout_optimizer.py`

1. Add a regression test using the real deterministic base renderer as Run178's fallback.
2. Use a public title longer than the legacy 34-character hook limit.
3. Make the layout provider fail once.
4. Assert one provider call, generated PNG exists, dimensions are 1280x670, and the embedded headline contract preserves the full exact title without ellipsis.
5. Run the focused test and verify it fails because the deterministic fallback raises the existing `ValueError`.

## Task 2 — GREEN: make deterministic renderer fit the full canonical title

**Files:**
- Modify: `editorial_eyecatch.py`
- Test: `tests/test_run178_eyecatch_editorial_layout_optimizer.py`

1. Separate public headline canonicalization from short hook generation.
2. For the public image headline, use the complete cleaned title after removing only the existing allowed leading bracket label.
3. Fit/wrap the complete title deterministically inside the existing headline region.
4. Never insert ellipsis or silently drop characters. If it genuinely cannot fit within bounded typography, fail closed.
5. Keep metadata/pixel binding through `eyecatch_publication_contract` unchanged.
6. Run the focused test and existing editorial eyecatch tests.

## Task 3 — cross-layer regression

**Files:** existing tests only unless a missing invariant is exposed.

Verify:
- Run178 valid-model-plan path still does not call fallback.
- Run178 provider failure remains exactly one provider call followed by deterministic rendering.
- synthetic mode remains zero-API.
- exact-copy rewrite rejection remains fail-closed.
- 1280x670 contract stays unchanged.
- headline pixel/metadata contract remains valid.

## Task 4 — wider verification

Run relevant eyecatch/publication suites, then full pytest and repository guards. If unrelated baseline failures occur, separate them from this change; do not broaden the patch opportunistically.

## Review focus

1. **Long headline still truncated:** caught by exact-title metadata/pixel contract assertion.
2. **Renderer silently shrinks below readability floor:** assert existing bounded font/geometry rules and fail closed if no fit.
3. **Provider retries increased:** assert exactly one optimizer provider call.
4. **Run178 model-rewrite protection weakened:** keep existing rewrite-rejection test unchanged.
5. **Publication contract bypassed:** use the real contract reader/validator in the regression rather than checking only file existence.

## Completion gate

The change is complete only when the new regression is GREEN, prior Run178/editorial/publication tests remain GREEN, broader tests/guards are GREEN, and no production-authority or Ready-policy code changed.
