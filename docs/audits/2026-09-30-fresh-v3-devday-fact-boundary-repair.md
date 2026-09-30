# Fresh v3 — source-bounded management fields before Local Skills compilation

## Reproducible failure and cause boundary

Observed in **Run 36688118222** (Fresh v2, 2026-09-30): requested discovery source HackerNews; candidate `OpenAI DevDay Recap – what's new`; structured provider fallback succeeded after two `gemini-3-flash-preview` errors; 5 model attempts total. Local Skills rendered an action mentioning `ChatGPT Plus`, and the unchanged Fact Gate returned `source-boundary unsupported named fact: ChatGPT Plus`. Editorial and Publication passed; Human Appeal ACCEPTABLE; **overall BLOCK**. The private artifact contains the rejected published-surface draft and gate diagnostics, **not the exact raw verification context**.

**Critical distinction:** OpenAI's September 29 official English DevDay recap *does* mention availability of GPT-6.1 Sol to API and Plus users. The observed gate result proves that `ChatGPT Plus` lacked support in the **runtime evidence context as validated by the existing source checker**; it does *not* prove the real-world claim was invented, nor does the public page prove the extraction contained that statement. The primary URL selected by the failed run was the Polish locale. The extraction/truncation versus cross-language lexical-match contributions cannot be separated from this artifact alone.

Primary links:
- Failed source: https://openai.com/pl-PL/index/devday-2026-recap/
- Parallel primary English page: https://openai.com/index/devday-2026-recap/
- Historical GitHub run: https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/36688118222

## Conservative repair

The current Production source-boundary checker is now supplied to the Local Skills **production adapter only**. Before compilation, it examines the provider's `decision_reason_text` and `action_text` against precisely the same `source_info.verification_context` passed later to the unchanged Fact Gate.

- If the original structured field is supported by the extracted evidence, **keep it verbatim**, including concrete plan/model names.
- If a field contains an unsupported named-product claim, replace **only that derived field** with a deterministic, source-neutral next-check/limited-validation statement. Log the exact preflight checker issue and the changed field in the private compile metadata.
- Do not synthesize new evidence from alternative-language pages. Do not use a broad alias exemption for `ChatGPT Plus`, nor weaken the source-boundary checker, Fact Gate, quality thresholds, Reader Value Gate, or existing deterministic numeric boundary.
- If verification context is missing, a checker reports an unknown error, or the deterministic replacement itself fails the original checker, fail closed **before compilation**. Any other unsupported claim in the rest of the article still receives the unchanged downstream Fact Gate.
- The provider-generated note article surface remains wholly discarded. The compiler's regenerated article and summary are synchronized from the *same scoped structured fields*.

This is a conservative loss-of-specificity tradeoff when evidence text is incomplete; it does **not** fix primary HTML ingestion in general. Broader language-aware source extraction should be evaluated separately with provenance-specific offline fixtures before altering the collector.

## Experiment integrity and budget

The DevDay article has already informed this repair. v3 quarantines its exact title and a locale-independent primary URL marker; it is a contaminated repair regression, **not a Fresh holdout**. v2's observed result is one **measured BLOCK** on HackerNews, with GitHub/ArXiv/OfficialVendor **UNMEASURED**. No v2 cross-source success is carried forward: independent v3 campaign starts at **0/4**.

Fresh v3 retains all v2 safeguards: one article candidate after the first provider send, Production 503/429 fallback within 6 pre-article + 4 article = 10 send slots, no quality rewrite or publication rescue, no article persistence, current Production source selection, unchanged Local Skills Writer and original final Gates. Manifest v3 fingerprints the newly active production adapter and unchanged source-boundary, excerpt, and parser modules; any drift fails before provider use.

All tests here are synthetic/zero Gemini. They verify the precise observed `ChatGPT Plus` lexical rejection, conservative fallback, explicit support retention, fail-closed missing evidence, unaffected Writer/Gates, and holdout quarantine. **No new v3 Fresh is executed in this PR.**
