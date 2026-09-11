# Defense Factory: bounded Stock persistence

This operation consumes the saved real Calibration observation for Defense Factory
(Raw 88, Final 88) through the canonical `production_pipeline.py` entrypoint. It
uses the existing `save_screening_metadata_to_notion` Production function to create
one metadata-only Stock record.

Safety contract:

- authoritative Notion URL dedup completes before the write claim;
- a create-only, non-expiring runtime-state claim prevents process/rerun duplicates;
- one Notion page-create call is allowed, with no retry on failure or ambiguity;
- source is `OfficialVendor`; X post 2097786616311840853 remains discovery provenance;
- Gemini credentials are blank and the process verifies zero model requests;
- no Deep Dive selection, article generation, publication or Telegram notification;
- the saved Final and observation file are pinned and fail closed if modified.

Six offline tests prove success, duplicate URL rejection, ambiguous-write behavior,
rerun rejection, tampered Final rejection and canonical entrypoint routing.

## Observed result

[Actions run 34601525320](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/34601525320)
completed successfully at 2026-09-11 12:56 UTC.

- The authoritative dedup read contained 1,144 URLs and did not contain Defense Factory.
- One Notion page was created: [Defense Factory](https://app.notion.com/p/3d8479ffdca981d2aff1f203bf02222f).
- A direct read-back verified Final/Decision 88, Screening 88, Stocked,
  Not Planned, Subscriber Only, OfficialVendor and Metadata Only.
- The page contains metadata only and no manuscript body.
- Gemini repository-local usage remained 5; this operation made zero model calls.
- Deep Dive selection, article generation, publication, Apify, FetchLayer and
  source fetching were not executed.
- The execution log is preserved as
  [Actions artifact 10264102884](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/34601525320/artifacts/10264102884).

The temporary push workflow was removed after success. Its executed source remains
in commit 2e6dbea87ec5fd27a067fc5ce43a95cf21a5fe06. The non-expiring runtime-state
claim remains and prevents this Stock authorization from being reused.

The next gate is a separately bounded Deep Dive generation decision using this
persisted page ID. It has not been authorized or executed by this Stock operation.
