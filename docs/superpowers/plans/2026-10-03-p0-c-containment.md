# P0-C Immediate Containment Implementation Plan

> Execute inline using superpowers:executing-plans. User explicitly authorizes implementation through PR, without merge.

Goal: close the four specified public boundaries without changing review, gate, routing or delivery decisions.
Architecture: retain internal captures and allowlists; publish only typed, allowlisted operational receipts. Remove raw upload steps, preserving producers and local consumers.
Tech stack: Python, pytest, GitHub Actions YAML.
Spec: user P0-C instructions, baseline a26eea5e0be5d4252b19fd535d2b664cc02e9e86; ROOT_CAUSE_REMEDIATION_DESIGN dated 2026-10-03.

## Constraints
No production execution, model requests, note/Notion mutations, infrastructure changes or auto-merge. P0 A/B and private storage remain unresolved.

## Root cause / impact
Daily parent reprints captured child streams (including TimeoutExpired), then dumps ordered_allowlist and arbitrary enrichment dictionaries. Daily upload steps directly select raw directories. Snapshot recovery copies failure.png into an Actions artifact. No repository download-artifact or gh run download consumer was found; external consumers remain unknown. Local gate_history consumer run624_delivery_causality.py must remain unchanged.

## Tasks
- [x] Add adversarial tests before changes: normal/timeout/provider failure/exception/malformed output, identity-bearing allowlist, all public sinks, raw directories and screenshot upload selection.
- [x] Record failing baseline with pytest.
- [x] Add operational_output_contract.py projection: explicit types/enums, no arbitrary values, safe error categories, known integer metrics and unknown request count.
- [x] daily_portfolio_review.py: preserve capture and safety checks; remove reprint, sanitize raised exceptions, project main output and capture dependent output. Retain internal allowlist.
- [x] Remove raw directory upload boundaries in Daily and identical regression route; replace with safe status receipt. Remove screenshot copy/upload and discard raw failure snapshot with safe status/count.
- [x] Verify alternate ordered_allowlist output in inventory bootstrap; retain internal list but remove public field.
- [ ] Regression: related unit, workflow/static, repository falsification/security, integration and current tests/ suite, offline only.
- [ ] Falsify all ten user scenarios, inspect diff and PR-trigger workflow safety; create PR only if gates pass; never merge.

## Review focus
Timeout partial bytes, malformed child shape, arbitrary enrichment result, alternate artifact glob, existing fail-closed safety detector. Every one receives an adversarial assertion.

## Verification checkpoint
24 containment tests pass; 140 related/security/integration tests passed before the final 5 supplementary cases. First full suite: 19 failed, 3297 passed, 512 subtests passed. Fresh lock hashes the entire Daily workflow; 11 failures cannot be resolved without changing the explicitly excluded Fresh contract. Baseline lock suite passes 18/18. The four loopback and two default-profile environment failures pass in an isolated temporary-profile rerun (28 passed, 9 subtests). Superseded artifact assertions and infrastructure-module registration were updated. Independent review could not start due to service usage limit. No PR or merge is authorized while these gates remain red.

Final CI-shaped full run: 11 failed, 3310 passed, 1 warning, 512 subtests passed in 153.63s. All failures are Fresh protocol lock tests. The final five supplementary containment tests were added after that full run collected tests; final containment run: 24 passed. Merge assessment: P0-C Immediate Containment NO-GO. Do not update the Fresh manifest without explicit scope extension.
