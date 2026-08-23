# Run110 Subscriber Inventory Portfolio Precision — Validation

## Purpose
Run109 live Plan exposed a launch-inventory ranking bias: top 4 were all ArXiv, top 20 were ArXiv-heavy, and all planned records surfaced authoritative Category=OTHER. Run110 fixes only the zero-API planning order; Adoption assessment remains authoritative Product Review.

## Falsification findings
1. A whole-window `max_source_share=0.60` does not constrain the first apply batch. A 50-row plan can satisfy the cap while ranks 1-4 are one source.
2. Legacy `Category=OTHER` is migration debt, not evidence that all candidates are truly uncategorized. Using it directly makes category diversification impossible.
3. Run109 rewarded recent ArXiv + long abstracts enough to outrank deployable tools with equal Screening Score.
4. Replacing this with fixed source quotas would create a different bias and could suppress genuinely valuable research/risk items.

## Run110 design
- `infer_planning_category()`: deterministic, plan-only inferred taxonomy; never writes or mutates authoritative Category.
- `candidate_lane()`: PRACTICAL / RESEARCH / RISK / DISCOVERY, plan-only. Security/governance research remains RISK rather than being generically deferred as research.
- `product_utility_score()`: favors concrete deployable/evaluable technology, mildly defers pure research for launch inventory, penalizes discovery/opinion noise. It is explicitly not Adoption Score.
- `plan_candidates()`: greedy marginal ranking with soft concentration penalties for repeated Source, Planning Category, and Lane.
- Source cap is prefix-aware: with 0.60, the first 4 can contain at most 3 from one source when alternatives exist.
- No fixed 60/25/15 portfolio quota and no forced ADOPT/TEST/WATCH/AVOID composition.
- Apply still sends only ordered canonical entity IDs to the existing Product Review authority.

## Validation
- New Run110 falsification tests: 7/7 PASS
- Bootstrap + Run109 integration + Run110 targeted: 31/31 PASS
- Full unittest: 487/487 PASS
- Full pytest: 487 passed + 10 subtests
- Synthetic Full: 500/500 PASS
- Synthetic critical failures: 0
- Synthetic major failures: 0
- production_write_isolation: true
- compileall: PASS
- GitHub Actions YAML: 6/6 PASS

## Safety / unchanged authority
Run110 does NOT change:
- Adoption Score or Adoption Status rules
- Product Review prompts/authority
- Evidence sufficiency
- History persistence
- Subscriber sanitization/sync
- Article generation, Fact Gate, Editorial Gate, Publication Readiness, Human Appeal
- Normal Daily candidate order
- Gemini budgets or Persistent Counter behavior

## Operational next step
Deploy Run110 and rerun `Subscriber Inventory Bootstrap` in `plan` mode only. Compare the first 4 and top 20 for Source/Lane/Planning Category diversity. Do not run apply until the new live Plan is reviewed.

## Package integrity
- Fresh unzip SHA256: 2578/2578 matched, 0 failed
- Release archive contains no pytest/regression runtime residue
