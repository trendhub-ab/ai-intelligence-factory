# X Discovery Ingestion PoC

This is an isolated **X -> Factory discovery** proof of concept. It does not write to the production Factory pipeline, does not call the official X API, and never treats an X post as evidence.

## Safety contract

- X posts are `discovery_only`; `is_evidence=false` is preserved in normalized signals and candidates.
- No imports or writes to the production Factory pipeline from the discovery runner.
- The offline provider and CI use local fixtures only and make zero external API calls.
- Apify is an optional, manually invoked provider adapter. It is not used by push CI.
- Live Apify runs require `APIFY_TOKEN` and `APIFY_ACTOR_ID` and are capped at 100 returned records in this PoC.
- The Apify request also sends `maxItems` and `maxTotalChargeUsd` run options as budget guards. Actor pricing and behavior remain provider-dependent.
- A third-party data provider is replaceable through `XDiscoveryProvider`; this code does not assume Apify is an official X integration.

## Data flow

`provider -> normalize -> post-id dedupe -> external URL extraction/canonicalization -> URL clustering -> isolated JSON artifacts`

The candidate artifact is `discovery_candidates.json`. `mention_count` counts distinct post IDs for each clustered resource, not URL occurrences or distinct authors. HTTP/HTTPS aliases in one post count once; two different posts count twice even from the same author. HTTPS remains preferred regardless of input order. `primary_source_candidate` is a conservative heuristic and is **not** evidence validation.

Primary-domain candidates are emitted to `primary_resolution_queue.json`. The inert `x_discovery.factory_adapter` validates that queue and emits a dry-run preview; it does not insert candidates into production screening.

## Offline run

```bash
python -m x_discovery.runner \
  --provider fixture \
  --output-dir /tmp/x-discovery \
  --max-records 20
```

Outputs:

- `raw_posts.json`
- `normalized_signals.json`
- `discovery_candidates.json`
- `manifest.json`
- `primary_resolution_queue.json`
- `provider_diagnostics.json` (and provider raw items when supplied by the provider)

To persist de-duplication across runs, add `--seen-ids /path/to/seen.json`.

## Live Apify smoke run

The GitHub Actions workflow `X Discovery Apify Smoke` is `workflow_dispatch` only. Configure repository secret `APIFY_TOKEN`, then supply the Actor ID and Actor input JSON manually. The normal offline workflow never consumes Apify allowance.

The provider calls Apify's synchronous Actor endpoint with Bearer authentication and never places the API token in the URL.

## Deliberately not implemented in this PoC

- automatic insertion of X-discovered candidates into normal Daily
- Evidence promotion
- automatic Notion writes from X discovery
- Factory -> X post generation
- X engagement feedback / Audience Interest Score
- automatic scheduling of the live provider

Those are separate integration steps after this isolated ingestion layer proves useful and stable.

## Offline validation, 2026-09-11

The distinct-post counting correction and historical replay are documented in [the validation record](docs/x_discovery_offline_validation_20260911.md). Four saved runs were replayed with networking blocked. Candidate identities and accepted URL sets were unchanged; Bootstrap had six overcounts corrected from two to one, including three primary-source candidates.

The production runtime at `c5a587183208ad44c9a95d27ac57ab867a6ac47d` was separately installed in a local offline probe. This is not a new live X dispatch lane. No provider calls, production writes, evidence promotion or generation were authorized by that probe.

## Bounded Factory validation, 2026-09-11

A separate, explicit saved-candidate validation lane now proves the integration boundary without turning X discovery into an automatic production source.

Defense Factory was used as the single saved candidate. The canonical Production entrypoint performed authoritative Notion URL deduplication and reached the installed Factory screening boundary. One bounded screening proof produced Raw Decision 88 / Commercial 90 / SECURITY while preserving X post `2097786616311840853` only as discovery provenance.

Current Production policy requires Global Calibration for Raw Score >= 55, so Raw 88 is **not** treated as a Final Score. Provider-free post-screening audit therefore returns `CALIBRATION_REQUIRED` and blocks Stock/Deep Dive until calibration completes.

A second provider-free counterexample audit exercises the real deterministic Deep Dive Stock guard:

- hypothetical Final 59, unpersisted -> not selected
- hypothetical Final 60, unpersisted -> not selected
- hypothetical Final 60 with a synthetic test-only persistence marker -> selected by the deterministic selector
- hypothetical Defense Factory Final 88, unpersisted -> not selected
- hypothetical Defense Factory Final 88 with a synthetic test-only persistence marker -> selected under the current threshold

Synthetic persistence markers are never written to Notion and do not claim that calibration or Stock persistence actually occurred.

Validation records:

- `docs/x_saved_candidate_screening_validation_20260911.md`
- `docs/x_post_screening_dry_run_20260911.md`
- `docs/x_post_calibration_counterexample_audit_20260911.md`

The next provider-using gate, if explicitly authorized, is one bounded Global Calibration request for the already-screened Defense Factory candidate. Screening must not be repeated, and Stock persistence, Deep Dive generation, and publication remain disabled during that validation.
