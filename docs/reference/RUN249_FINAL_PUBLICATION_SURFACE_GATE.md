# Run249 — Final Publication Surface Gate

## Purpose

Run248 correctly strengthened Reader Value and first-real-publish quality, but the first post-Run248 real `article_validation` exposed a later publication boundary: `title_text` and the reader-first `30秒でわかるこの記事` summary are assembled into the final note manuscript after the normal generated-article quality gates. A generated body could therefore pass the existing gates while the final public surface still contained reader-material defects.

Run249 closes only that late-stage hole. It does not redesign article generation, Evidence, Decision, eyecatch background, model order, quota, or note release behavior.

## Production contract

Run249 is installed after Run248 and before Run194 Publication Contract.

Before a candidate can remain publication-eligible, the existing Human Appeal evaluation now also inspects a deterministic projection of the final public note surface:

- public title
- `30秒でわかるこの記事` / `何が出た？` / `なぜ重要？` / `結論は？`
- article body

The projection is evaluated with the existing zero-API Reader Experience diagnostics. Broad corroborated weakness continues to use the existing `reader_value_review:` path and therefore routes the item to `Needs Editorial Review`; it does not spend an extra Gemini retry merely to force publication yield.

## High-confidence late-surface failures

Run249 fails closed on the following narrow defects:

1. orphan or unbalanced Japanese title brackets (`「」`, `『』`)
2. a standalone 30-second-summary answer that visibly ends as a fragment with `、`, `，`, or `,`
3. existing Run248 multi-axis Reader Experience weakness detected on the final public projection
4. existing Run248 high-confidence broken-Japanese signals detected on the final projection

The exact real specimen that escaped Run248 is locked into regression tests, including the orphan `」` title and incomplete `何が出た？` / `なぜ重要？` answers. This real-specimen regression is part of the normal zero-API test suite and must remain green before Run249 can enter `main`.

## Presentation-only deterministic repair

If the canonical article disclaimer is glued directly to the preceding supplemental Evidence Markdown link, Run249 inserts a blank line. This changes presentation only and does not alter the Evidence URL, claim, Decision, or disclaimer text.

## Cost and safety

- additional Gemini/provider calls: **0**
- Evidence semantics changed: **false**
- Decision semantics changed: **false**
- eyecatch background/right-side illustration changed: **false**
- public note release automated: **false**
- Daily resumed: **false**

## Publication provenance

`run249_final_publication_surface_gate.py` participates in `publication_contract.PUBLICATION_POLICY_FILES`. Any Run249 code change therefore changes the policy fingerprint, making older Ready manuscripts stale until they are regenerated under the current policy. `Note Ready Article Sync` also watches Run249 policy/test changes so the human-facing queue is reconciled immediately.
