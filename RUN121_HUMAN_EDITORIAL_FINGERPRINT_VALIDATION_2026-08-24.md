# Run121 Human Editorial Fingerprint / Cross-Article Naturalness Gate Validation — 2026-08-24

## Decision
PASS — Article quality logic completion baseline candidate.

## What changed
- Added zero-API Human Editorial Depth signals for repeated explanation, excessive explicit transitions, and repeated explanatory closers.
- Added run-local Cross-Article Naturalness Gate based on rhetorical fingerprints rather than topic vocabulary.
- Added `APPEAL_CROSS_ARTICLE_FINGERPRINT` as REVIEW severity and targeted existing Quality Retry guidance.
- Added run-local bounded style memory, production-run reset, and nonpersistent-regeneration isolation.
- Deterministic publication rescue now re-runs Human Appeal with the same peer memory so rescue cannot bypass the cross-article gate.
- Prompt guidance now explicitly forbids unnecessary re-explanation, over-signposted transitions, and generic introductions reusable across unrelated articles.

## Falsification targets
1. A natural human-edited article must not fail merely because it contains one contrast or one repeated decision stance.
2. Technical vocabulary overlap must not by itself trigger cross-article similarity.
3. A near-clone article with changed nouns but the same introduction/section/decision rhythm must be detected.
4. Rephrasing the same explanation several times plus transition overuse must be detected.
5. Cross-article defect must remain REVIEW, not HARD Fact failure.
6. Quality Retry may change structure/order but may not invent facts, numbers, entities, or change Decision meaning.
7. Deterministic rescue must not erase a different defect and then bypass the cross-article review.
8. Test/Regen paths must not be contaminated by production run memory.
9. No new Gemini request path may be introduced.

## Validation results
- Run121 dedicated tests: 10/10 PASS.
- Full unittest discovery: 594/594 PASS.
- pytest: 594 passed + 19 subtests.
- Synthetic Full: 500/500 PASS; critical failures 0; major failures 0; production_write_isolation=true.
- Mutation Negative Control: 3/3 KILLED.
  - Cross-article threshold disabled -> KILLED.
  - Cross-article issue suppressed -> KILLED.
  - Deterministic rescue peer-memory bypass -> KILLED.
- compileall: PASS.
- Existing Run108 natural editorial sample remains non-high AI style.
- No additional Gemini call site introduced.

## Product judgment
This closes the main remaining quality gap: a single article can read naturally while a run of articles still exposes a repeated AI editorial fingerprint. Run121 detects that run-level repetition without adding model cost or weakening Fact/Evidence gates. Further prose-rule additions should now require real production article evidence rather than speculative polishing.

## Final package checks
- Production `_generate_via_chat(` call sites: 7 (unchanged from Run120).
- Production `genai.Client(` sites: 1 (unchanged from Run120).
- Workflow YAML files: 8/8 parsed.
- Fresh unzip SHA256: 2622/2622 PASS.
- Markdown UTF-8: 2054 files PASS.
- Japanese canonical spec ZIP UTF-8 flag: PASS.
- Mojibake filenames: 0.
