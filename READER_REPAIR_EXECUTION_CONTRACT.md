# Reader Repair Execution Contract — Run359

## Purpose

The 2026-09-12 RubyGems Production specimen showed that authorizing a Reader repair is not enough. The repair model could preserve the same technical-name inventory, produce a superficially revised article, and then fail Reader or final-summary review again.

Run359 does not relax the gate. It makes the existing bounded repair instruction operational.

## Behavior

When the actual Reader reason is density/non-engineer access weakness, the repair must delete or category-compress technical names that do not change Decision, important limitations, or primary Evidence meaning. If three or more specialist names/abbreviations remain in one paragraph, each must be necessary to the Decision; otherwise they are compressed or removed.

When `final_surface_summary_jargon_cluster` is present, the repair targets the source sentences from which the deterministic 30-second summary is built: source summary, intro, why, conclusion, final/action. This avoids trying to repair a late deterministic summary after the model call.

The contract explicitly forbids solving jargon by adding more jargon explanation. The required edit is deletion/compression first, then one plain-language bridge where necessary.

## Safety invariants

- no new provider/model call;
- no new retry budget;
- Evidence must already be SUFFICIENT and decision-scope safe for the fresh Reader-only retry path;
- Fact/Evidence/Publication gates remain unchanged and rerun after repair;
- no threshold reduction;
- no automatic Ready conversion;
- no Groq routing change;
- targeted directives appear only when their corresponding Reader reasons are present.

## Expected outcome

Run359 should increase the probability that the one already-authorized Gemini quality repair actually removes the cause of `technical_term_concentration`, `jargon_translation_weak`, `non_engineer_access_failure`, and final-summary jargon clustering, instead of spending the call on cosmetic rewriting.
