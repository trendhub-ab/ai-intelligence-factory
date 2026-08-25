# Run114 Inventory Bootstrap Operations

Run114反映後の最初の実地確認は、Inventory Bootstrap Applyを1回だけ実行する。

推奨workflow inputs:

```text
mode: apply
target_inventory: 30
min_sellable: 24
max_reviews: 3
product_request_budget: 6
max_source_share: 0.60
confirm: CONFIRM_BOOTSTRAP
```

確認項目:

1. Evidence preflightで`evidence_ready`が最大3件へ到達すること。
2. Product Review logでSchema利用による通常JSON成功を確認すること。
3. JSON崩れが発生した場合は`structured_retries`が最大該当候補数だけ増え、同じ候補の`review_slots_used`が二重計上されないこと。
4. Source Boundary False Rejectが出た場合、`boundary_reconciliation_attempted`が増えること。
5. 公式Docsで根拠が確認できた場合だけ`boundary_reconciled`が増え、その後保存されること。
6. 外部host・根拠なしの場合は保存されないこと。
7. Subscriber Sync / Decision Historyが保存成功件だけ増えること。
8. Screening / Calibration / article Deep Dive / Quality RetryなどBootstrap外のGemini pathが走らないこと。

Run114の最初のApplyでは`max_reviews=3`を増やさない。Structured retryが必要な場合に備え、`product_request_budget=6`を維持する。
