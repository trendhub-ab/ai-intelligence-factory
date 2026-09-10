# X Discovery Ingestion PoC

This is an isolated **X -> Factory discovery** proof of concept. It does not write to the production Factory pipeline, does not call the official X API, and never treats an X post as evidence.

## Safety contract

- X posts are `discovery_only`; `is_evidence=false` is preserved in normalized signals and candidates.
- No imports or writes to the production Factory pipeline.
- The offline provider and CI use local fixtures only and make zero external API calls.
- Apify is an optional, manually invoked provider adapter. It is not used by push CI.
- Live Apify runs require `APIFY_TOKEN` and `APIFY_ACTOR_ID` and are capped at 100 returned records in this PoC.
- The Apify request also sends `maxItems` and `maxTotalChargeUsd` run options as budget guards. Actor pricing and behavior remain provider-dependent.
- A third-party data provider is replaceable through `XDiscoveryProvider`; this code does not assume Apify is an official X integration.

## Data flow

`provider -> normalize -> post-id dedupe -> external URL extraction/canonicalization -> URL clustering -> isolated JSON artifacts`

The final artifact is `discovery_candidates.json`. A repeated canonical URL increases `mention_count`; this is a discovery signal only. `primary_source_candidate` is a conservative heuristic and is **not** evidence validation.

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

To persist de-duplication across runs, add `--seen-ids /path/to/seen.json`.

## Live Apify smoke run

The GitHub Actions workflow `X Discovery Apify Smoke` is `workflow_dispatch` only. Configure repository secret `APIFY_TOKEN`, then supply the Actor ID and Actor input JSON manually. The normal offline workflow never consumes Apify allowance.

The provider calls Apify's synchronous Actor endpoint with Bearer authentication and never places the API token in the URL.

## Deliberately not implemented in this PoC

- Factory Screening insertion
- Evidence promotion
- Notion writes
- Factory -> X post generation
- X engagement feedback / Audience Interest Score
- automatic scheduling of the live provider

Those are separate integration steps after this isolated ingestion layer proves useful and stable.
