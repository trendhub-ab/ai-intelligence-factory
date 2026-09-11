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

Execution outcome: pending. This document does not claim that Stock was saved.
