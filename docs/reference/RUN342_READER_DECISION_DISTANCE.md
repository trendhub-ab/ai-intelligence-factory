# Run342 Reader Decision Distance

## Why this refinement exists

Run341 fixed the control-policy defect that prevented reader-only repair in fresh Production and constrained mixed retries. A live `article_validation` against the real IBIB candidate was then attempted on 2026-09-10, but Gemini 3.7 Flash and 3.8 Flash returned confirmed HTTP 503 pairs and the validation produced no new manuscript. Re-running immediately would spend provider budget without adding evidence.

Instead, Run342 replayed the prior full-Daily private audit artifact (`private-gate-review-39`) containing the exact IBIB and DeepSeek manuscripts that triggered Run341.

The replay exposed a more precise reader-experience failure: a manuscript can contain a friendly rhetorical question and an analogy yet still delay the reader's actual use decision. The old opening heuristics reward proximity markers such as questions and analogies, but those markers do not by themselves answer the reader's business question: **what changed, why does it matter to me, and what should I do now?**

## Production refinement

Run342 stays inside the existing canonical `run208_reader_value_repair.py` layer. No new runtime wrapper, provider route, retry loop, or gate is added.

The first-pass Reader Path now requires the following semantic information to appear within the first three paragraphs, without fixed headings or canned phrases:

1. what changed;
2. why the change matters to the reader's work or use decision;
3. a provisional action/decision such as try, compare, wait, or pass.

A rhetorical question or analogy is explicitly insufficient by itself. If used, it must immediately connect to the decision. Technical identifiers and implementation details that are not needed for the provisional decision are pushed behind that early decision bridge. Numeric evidence must be introduced by explaining what decision the number affects, unless the number itself is the news.

## Reader Repair refinement

When a Reader Value retry is already authorized, the repair contract may move an existing later Decision/Action sentence into the opening without changing its meaning. It may compress or remove a rhetorical hook or analogy when that device delays the decision, and may reorder existing technical detail after the decision bridge.

The repair may not add new facts, numbers, products, experiences, causality, guarantees, Evidence meaning, Decision semantics, Score, or Action. Fact, Evidence, Publication, and Reader gates still rerun after repair and remain fail-closed.

## Compatibility

- Existing Run208 Pending Retry behavior is preserved.
- Run341 fresh-Production authorization remains unchanged.
- Fixed heading templates remain prohibited; only semantic ordering is constrained.
- `run208_reader_value_repair.py` is already part of the Publication Contract fingerprint and Note Ready policy-change reconciliation, so these changed bytes automatically invalidate stale Ready provenance.
- No note/customer-facing mutation is performed by this change.

## Cost policy

Run342 adds zero provider calls. The failed live validation is not blindly retried while confirmed 503s persist. The next ordinary Production/validation call will naturally test the refined prompt when the provider is available.