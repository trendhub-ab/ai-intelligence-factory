# Defense Factory: Stock to Deep Dive handoff

The saved Stock observation was passed through `production_pipeline.py` and the
canonical Production `_select_stocked_deep_dive_candidates` policy.

Observed result:

- Final Score: 88
- persisted Notion page: `3d8479ff-dca9-81d2-aff1-f203bf02222f`
- result: `DEEP_DIVE_SELECTION_READY`
- Deep Dive selected: true
- Gemini/model calls: 0
- Notion writes: 0
- article generation/publication: false

The same contract rejects a record with no persisted page ID. This proves that the
previously created real Stock, rather than a synthetic persistence marker, satisfies
the Deep Dive selector. It does not generate an article or authorize publication.
