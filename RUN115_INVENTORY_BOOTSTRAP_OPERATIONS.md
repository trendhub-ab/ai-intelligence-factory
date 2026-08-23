# Run115 Inventory Bootstrap Operations

## Purpose
Run115の実Provider E2Eを、在庫構築を兼ねて最小コストで確認する。

## Recommended GitHub Actions input

```text
mode: apply
target_inventory: 30
min_sellable: 24
max_reviews: 3
product_request_budget: 6
max_source_share: 0.60
confirm: CONFIRM_BOOTSTRAP
```

`max_reviews=3`はEvidence-ready候補のGemini review slot上限。Evidence不足候補はRun113仕様どおりreview slotを消費しない。`product_request_budget=6`は3候補それぞれがstructured-output repairを最大1回必要とする最悪ケースを収容する上限であり、通常は6回使い切ることを目標にしない。

## Apply後に必ず見る項目

1. `inspected` / `evidence_ready` / `review_slots_used` / `saved`
2. `structured_retries` / `structured_retry_recovered`
3. `boundary_reconciliation_attempted` / `boundary_reconciled`
4. Product Review Gemini Requests Used と `by_kind`
5. Gemini API Attempts / model / tokens
6. saved候補のCategory / Adoption / Evidence / Readiness
7. Decision History INITIAL/CHANGE記録
8. AI Decision Intelligence subscriber sync
9. `unsafe_activity=[]`および記事生成系がBootstrap中に走っていないこと

## Expected safety behavior

- Provider JSONがSyntax/Semantic Schema違反なら、budgetがあれば同一候補だけ1回retry。
- budgetがなければ2回目を送信せずFail-Closed。
- unsupported named factだけSource-Boundary Reconciliation対象。
- official Seedがthird-partyへredirectした場合、その本文はEvidenceとして使わない。
- named factがfirst-party sourceで確認できない場合は保存しない。
- Category等のSchema違反を`OTHER`等へ黙って補正しない。
- Evidence Gate / Primary Source Authority / Decision validatorは緩和しない。

## Stop conditions

以下のいずれかが出たら連続Applyを止め、Artifactを監査する。

- Product Review request usageが入力上限を超える
- third-party redirect URLが`Primary Evidence URLs`へ入る
- Schema違反候補がretryなしで保存される
- `review_slots_used`より多数の候補がGemini評価される
- Subscriber rowは増えたがHistoryが生成されない
- `unsafe_activity`が空でない
- 通常記事Deep Dive / quality retryがBootstrap中に発生する

## Plan mode
Planは引き続き0 Gemini / read-only。候補順位・portfolio balanceを確認する用途であり、Run115 Structured Output / Boundary Reconciliationの実Provider検証にはApplyが必要。
