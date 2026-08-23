# Run116 Inventory Bootstrap Operations

Run116はRun115と同じBootstrap input contractを使う。Source-Boundary Reconciliationは自動で0-Gemini bounded discoveryを行うため、新しいGitHub Variable/Secretは不要。

## Recommended controlled Apply

- `mode`: `apply`
- `target_inventory`: `30`
- `min_sellable`: `24`
- `max_reviews`: `3`
- `product_request_budget`: `6`
- `max_source_share`: `0.60`
- `confirm`: `CONFIRM_BOOTSTRAP`

## Expected invariants

- Evidence不足候補はGemini review slotを消費しない。
- Product ReviewはEvidence-ready最大3件。
- Structured retryは同一候補最大1回、既存Product Review budget内のみ。
- Boundary Reconciliationはnamed-fact failure時だけ。
- Boundary Reconciliation Gemini requests: 0。
- Discovery fetch <= 3 / body fetch <= 6 / ranked candidates <= 4。
- Third-party sitemap/link/redirectはEvidenceに入らない。
- named fact完全名を本文で確認できない場合はFail-Closed。
- 保存成功時のみHistory / Subscriber Syncへ進む。

## Artifact audit

`*_inventory_bootstrap_pipeline.log`で以下を確認する。

- `[PRODUCT REVIEW BOUNDARY RECONCILIATION]`
- `resolved`
- `body_fetches`
- `discovery_fetches`
- `discovered_urls`
- `ranked_candidates_considered`
- `Product Review Gemini Requests Used`
- Subscriber sync created / updated / unchanged

Apply後はInternal Technology Intelligence DB、AI Decision Intelligence、Decision Historyの3箇所を突合する。
