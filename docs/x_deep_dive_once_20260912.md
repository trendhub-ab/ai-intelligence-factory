# Defense Factory bounded Deep Dive — 2026-09-12

## Result

The saved X-discovered Defense Factory item reached the real Production Deep Dive provider boundary from its already-persisted Stock page.

No article was produced because the single permitted `gemini-3.6-flash` HTTP attempt returned `503 UNAVAILABLE` with a temporary high-demand message.

This is a provider-availability result, not an article-quality result. Article quality is therefore inconclusive.

## Attempt 1 — pre-model stop

- workflow run: `34618877079`
- job: `103327550998`
- model calls: `0`
- operation claim: not created
- reason: the bounded preflight inherited Production freshness logic that required a separate follow-up page even though the canonical official primary page was live and retrievable.

The run stopped before the irreversible provider claim, so no Gemini request was spent.

## Bounded freshness correction

The global Factory Evidence/Freshness policy was not relaxed.

Only `x_discovery.deep_dive_once` was changed for this one-item validation lane: when the candidate source is `OfficialVendor`, the canonical official primary page was successfully resolved live in the same run, and no separate follow-up page exists, that live primary retrieval is explicitly recorded as `live_official_primary_fetch` and is accepted as bounded freshness evidence.

Provider-free `X Bounded Validation CI` passed after this change.

## Attempt 2 — one provider request

- workflow run: `34619269692`
- job: `103328865894`
- artifact: `10272101192`
- artifact digest: `sha256:609f669732c21ba834827d09e636a88cf5e75bed830f0348bc7b3ee25d0b3ca2`
- model: `gemini-3.6-flash`
- persistent repository-local model counter at reservation: `12/18`
- local operation budget: `1/1`
- SDK HTTP attempts: `1`
- provider result: HTTP `503`, `UNAVAILABLE`
- retry: none
- fallback: none
- article characters: `0`
- status: `DEEP_DIVE_NO_ARTICLE`

The provider message stated that the model was experiencing high demand and suggested trying again later. The bounded contract intentionally did not retry.

## Safety result

The operation-wide create-only claim now exists at:

`.runtime/operations/defense-factory-deep-dive-20260911.json`

with status `claimed_no_reissue` and run ID `34619269692`.

Therefore this operation is permanently spent and must not be reissued under the same authorization, even though the provider returned 503.

The temporary provider-capable workflow was removed immediately after the result.

Throughout the Deep Dive attempt:

- Screening re-execution: false
- Calibration re-execution: false
- Stock persistence re-execution: false
- Notion writes: 0
- Factory article writes: 0
- eyecatch generation/upload: disabled
- note draft/publication: 0
- X remains discovery-only, not evidence

## What is proven

The integration path is now proven through one real Deep Dive provider attempt:

`X discovery -> primary URL -> Factory dedup -> Screening -> Global Calibration -> Stock -> persisted Notion page -> Production Deep Dive selection -> live official-source evidence/freshness preflight -> one real Deep Dive provider request`

What is **not** proven is article quality or article persistence/publication, because the model returned no output.

## Next decision

Do not automatically retry this operation. Any later article-generation attempt requires a separate explicit decision and a new bounded operation identity. The previous operation claim must remain immutable as an audit record.
