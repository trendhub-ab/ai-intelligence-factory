# Naturalness v2 + Ready Yield Guard

Base: `6e87d266cbe1298c4e9407288d4a85e6c0e25477`
Branch: `feat/naturalness-v2-ready-yield-guard`

## Implementation

- Add deterministic advisory diagnostics for repeated first-person section endings, meta summaries, grand closings, and uniform section length.
- Recommend editing only when at least two independent habits overlap. Ignore fenced code, block quotations, Japanese quoted text and standard summary/source sections.
- Attach located advice only to an existing Quality Retry. Preserve facts, evidence, decisions, quantities, URLs, conditions, limitations and information volume.
- Diagnose the actual polished `previous_article` supplied by the pipeline, not the cached raw parse. Reset the article on each prompt/generation.
- Preserve provider fallback and retry authorization. No new Gate/reason, score/threshold change, provider call or retry loop.
- Keep `local_skills/a_plus.py`, pipeline, workflows and the Fresh manifest unchanged. Fresh has zero Quality Retries, so this advice does not alter its generated prompts.

## Verification ledger

- RED: 7 new feature assertions failed before implementation; 2 unchanged-path checks passed.
- GREEN: initial related suite 27 passed.
- Independent review: found raw-versus-polished section-number mismatch. Reproducer failed first; fix uses actual previous_article. Related suite 28 passed.
- Added provider-unavailable fallback invariant test: local manuscript still returned after one provider attempt.
- First whole active suite: 3517 passed, 11 Fresh lock failures caused by placing the contract builder in frozen local_skills/a_plus.py. Restored that file byte-for-byte and moved the builder to editorial_naturalness.py. No manifest re-fingerprinting.
- Fresh lock + targeted tests after relocation: 44 passed. Fresh lock verified all 30 fingerprints; Publication Dependency Completeness PASS (71 files).
- Legacy style/depth detector outputs matched main on all 6 stored Markdown fixtures.
- Root-level bare pytest also collects retired archive tests and fails importing missing run153_backfill_catalog; active suite is tests/.

## Decisions and limitations

- v2 is advisory only, deliberately separate from existing score/high fields. This protects eligibility; actual production Ready yield or prose improvement is not measured by offline tests.
- Keep frozen local_skills/a_plus.py unchanged; the pure contract builder lives beside diagnostics instead. Cost: the helper location differs from the first implementation, without changing the public fallback API.
- Deferred minor from review: grand-closing phrases inside a negated claim may still produce advice when another repeated habit is present. Advice is not a Gate and explicitly preserves facts and conditions.
- No live generation, workflow dispatch, note/Notion write, main update or merge performed.

## Final result

- Final active suite: `python -m pytest -q tests` — **3530 passed**, one existing Pillow deprecation warning, 154.65 seconds.
- Runtime: `/usr/bin/python3` 3.12.3 with the existing audit and primary-runtime dependency directories on PYTHONPATH; no package installation or provider traffic.
- `git diff --check`: PASS.
- Main re-read before saving remained `6e87d266cbe1298c4e9407288d4a85e6c0e25477`.
