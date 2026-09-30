# Fresh v2 — 503 fallback retained, hard model-send budget (2026-09-30)

## Why a new protocol version is necessary
The historical Stage 3 v1 manifest called its article stage "at most one Deep Dive send," but Production's `_call_model_pool` can make multiple *physical provider send attempts* under 503/429 fallback. Model fallback is essential during 503 storms and must be preserved, not conflated with a single article-analysis task.

v2 is therefore **an independent four-source measurement protocol, starting at 0/4**. The v1 result remains historical: HN 1/4 measured PASS, three sources UNMEASURED. Do not carry that HN PASS into v2.

## Enforced per-run rules
- Reuse the registered v1 four-source acquisition, legal, dedupe, unchanged Local Skills Writer/Canonicalizer/Evidence Boundary, Production Screening/Calibration/selection, and all unchanged quality Gates.
- A validated new candidate may be backfilled before a provider article send without consuming an article send slot. After **any attempted article-model slot on one candidate**, never try a second candidate, even on 503 or failure. One article's *same prompt* can use Production's healthy-model fallback.
- Keep `MAX_QUALITY_RETRIES=0` and deterministic publication rescue disabled, as in v1. No note/Notion manuscript persistence.
- Install a scoped **pre-send** hard guard around the final `pipeline._generate_via_chat` call only for Fresh. It reserves at most **6 Screening/Calibration slots + 4 Deep Dive slots = 10 total slots**, shared across ALL actual model choices and same-model retries. A fifth Deep Dive or seventh pre-article attempted send is rejected *before* calling the underlying provider function. A later stop records UNMEASURED, not Gate FAIL/PASS.
- The underlying health-aware pool order, structured 503, per-model RPD/RPM limits, timeouts and configured fallback models are not changed. Provider SDK attempt ownership remains Production's separately validated single SDK attempt; if that safety contract is modified, v2 requires a new fingerprint.
- Fresh logs guarded reservations, attempted model list, cap and measurement status separately from actual `GEMINI_USAGE_AUDIT` transport records. A slot can be conservatively reserved when the downstream sender rejects before HTTP, so reserved slots are an **upper bound**, not proof of exact API bills. Current vendor RPM/RPD remaining is NOT_MEASURED.

## Operator gate
The offline `fresh_protocol_quota_lock.py` checks manifest v2: hashes for Local Skills, Production orchestration, gates, the actual model routing module, provider resilience, the scoped guard and the original source-stratified canary; it rejects drift and unapproved budgets. It **does not** fetch fresh articles or call Gemini.

Even with the hard stop, running the source-filtered canary currently collects *all four sources* and queries authoritative Notion. Do not start until the user's constrained quota has actually recovered. The manual zero-Gemini source preflight is a separate option when only source/Notion reads are permissible.

## Test coverage
Mocked real provider-resilience 503->healthy-model fallback, a multi-503 storm refusing an extra call, pre-article saturation, v2 manifest mutations, one-candidate/no-rewrite semantics, and restoration of the original Production provider function are required. No LIVE Fresh/ Daily test is necessary for this code-change approval. Passing offline tests do not prove v2 source-stratified 4/4.
