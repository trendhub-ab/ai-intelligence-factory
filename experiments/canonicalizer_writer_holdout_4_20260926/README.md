# Stage 5 — Frozen Canonicalizer + Local Writer blind holdout

Selection was committed before any Gate execution.

- Publication Canonicalizer v3 blob: `6030016136e905d3c611fe93425a7f11133c3028`
- Local Writer v3 blob: `dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2`
- Selection commit: `199d9e3831aec51366cfd99cf498be9233b131ce`
- Stage 1-4 records excluded: 24
- Current unused eligible records: 4
- Existing article body used for selection: **false**
- Provider/LLM API calls: **0**
- Production/Gate changes: **none**
- Notion writes: **none**
- note publication: **none**

## Selection rule

Use every currently eligible structured record that was never used in Stages 1-4. Do not weaken the evidence or structured-field eligibility rules to enlarge the sample. The seeded FNV-1a hash controls execution order only; it does not control inclusion.

Source mix: ArXiv 2 / HackerNews 2.

## Primary metric

Exact all-Gate pass rate through the frozen Publication Canonicalizer v3 + frozen Local Writer v3 + unchanged Production Fact / Editorial / Publication / Human Appeal stack.

Primary success criterion for this holdout is **4/4**. Because n=4 and source diversity is limited, even 4/4 is evidence of out-of-development-set generalization, not final Production proof.

Any failure is a finding. Do not tune Canonicalizer v3 or Local Writer v3 on this holdout before the primary result is recorded.

Draft / Do not merge.
