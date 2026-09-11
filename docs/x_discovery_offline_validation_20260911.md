# X Discovery offline validation — 2026-09-11

## Scope and source revisions

- X source baseline: `b0557b9b0ffed4bd9c716a5a4fa699150ce97849`.
- Production runtime baseline: `c5a587183208ad44c9a95d27ac57ab867a6ac47d`. The 200 root Python source files were retrieved and verified against their Git blob hashes.
- This branch remains isolated from main. No new X acquisition or live Factory dispatch is part of this change.

## Counting correction

`cluster_candidates` used to increment `mention_count` for each URL occurrence. Its identity function already merged HTTP/HTTPS aliases, so one post could count twice. Increment only when adding a previously unseen post ID to the candidate. Continue processing URL preference and metadata so HTTPS selection does not depend on input order.

No candidate identity, allowlist, evidence flag, network behavior or Factory input insertion logic is changed. Historic artifacts are immutable evidence; regenerate downstream queues from saved raw posts to obtain corrected counts. Old queues are not silently rewritten.

## Historical replay

| Actions run | Stored posts | Candidates | Adapter accepted | Count corrections |
|---|---:|---:|---:|---:|
| 34489727088 | 3 | 2 | 2 | 0 |
| 34492200482 | 1 | 0 | 0 | 0 |
| 34493159794 | 5 | 0 | 0 | 0 |
| 34495658282 | 84 | 36 | 30 | 6 |

For Bootstrap, reward-seeker, Shieldstral and Stable Audio are the three primary-candidate corrections. The other three are luma.com/together-s3r6, muse.ai and security.muse.ai. All six change from 2 to 1. Candidate fields other than mention_count and candidate ordering are unchanged; accepted URL sets are unchanged. The runner reuses historical resolved URLs; no HTTP redirect replay is claimed.

37 X unit tests pass, including five new regression cases covering scheme order, repeated signals, separate posts by one author, separate targets and candidate ranking. The original source fails the new regression suite. Network access is blocked during historical replay and the production probe.

## Installed production runtime probe

The actual `production_pipeline.main` installed its normal runtime layers and current overlays. `pipeline.main` was replaced by a local probe, and synthetic mode skipped live startup preflight and font download. No production source files were modified for the probe.

The probe exercised installed normalization, source rotation, legal gate, existing-URL extraction, source preparation, evidence supplementation, evidence sufficiency, and screening batching. The exact main-body URL dedupe block was executed with installed runtime functions. This is not a full Daily execution.

The Content Intelligence snapshot contained 1,168 non-archived rows across 12 pages, with the final has_more=false. Replaying its visible URL properties through the real existing-URL function produced 1,144 canonical URLs. All three reviewed candidates remained; added batch duplicates and known URLs were removed. A simulated query failure returned None. The associated Telegram alert was captured locally, not sent.

Source preparation used saved web-extracted text rather than Factory HTTP/HTML/PDF transport. Supplementary papers were partial extracts. All three candidates reached SUFFICIENT at LOW action risk through installed runtime functions; a missing-body counterexample did not. These are evidence-sufficiency results, not content quality scores or publication approvals.

The single Defense Factory candidate reached `call_screening_provider` through the real screening batching function. A deliberate local sentinel stopped there, before model routing or any request. No model output or score was fabricated. Model calls 0, network attempts 0, external writes 0, Ready 0.

## First live trial, when separately authorized

Choose Defense Factory: its official page was sufficient without supplemental fetching. Use the saved candidate and the official primary URL, preserve X post ID `2097786616311840853` as discovery provenance, and keep its X engagement separate from Factory scoring.

Current production has no saved-X-input dispatch lane; article_validation targets existing Notion rows and cannot be used as though it accepted this new external candidate. A bounded lane through the canonical production entrypoint must be designed and tested before live execution. It must take exactly one explicit candidate, fail closed if dedup cannot be verified, and persist no content during validation. Do not use normal Daily or write a Notion row merely to bypass this missing input path.

Do not infer that one candidate consumes one Gemini request: screening, calibration, generation and existing retries/quality repairs have separate budgets. Fix and disclose a total request ceiling before authorizing the trial. Keep Apify/FetchLayer calls at zero, preserve existing quota guards and publishing gates, and never merge this isolated branch into main automatically.

Machine-readable replay and runtime results and the local probe are provided in the accompanying validation bundle. Public-source text caches are not redistributed; hashes and extraction ranges identify the inputs used. Full live preflight, exact REST rich-text responses, model behavior, generation and publication remain untested.
