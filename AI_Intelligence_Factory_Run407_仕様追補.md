# AI Intelligence Factory Run407 仕様追補

## 実運用で判明したこと
Run #7（34757852062）では、RubyGems記事について Gemini 3.8/3.7 が503、3.6が成功した。初稿はPublication Readiness PASS。その後のReader Repairも3.6で成功したが、再判定後に `dense_report_cluster`、`multi_axis_reader_weakness`、`non_engineer_access_failure` の3件がReader-only REVIEWとして残った。

Run406は追加Reader Repairを `multi_axis_reader_weakness` 単独残存時だけ許可していたため、この実際の3件セットでは5本目のリクエストを使わず `run360_reader_repair_already_spent` で停止した。

## Run407変更
Run399のowner-approved exact-target laneに限り、追加1回のReader Repair対象を次のReader密度系残存理由へ拡張する。
- `dense_report_cluster`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`

ただし `multi_axis_reader_weakness` を必須とし、全blocking rowが上記3種のいずれか、すべてReader Value REVIEW、Evidence=`SUFFICIENT`、`decision_scope_safe=true` の場合だけ許可する。

## 変更しないもの
- API request budgetは5のまま。増やさない。
- 追加Reader Repairは最大1回。3回目は不可。
- 通常Daily / article_validation / pending_retryのRun360契約は変更しない。
- Fact / Evidence / Publication / Reader Gateの閾値は変更しない。
- HARD、score mismatch、final-surface等の未観測理由を追加修復対象へ含めない。
- Decision Score、Evidence、数値、重要制約を緩和しない。
- Xロジックは変更しない。
- note公開は行わない。Ready後の到達点はprivate draftまでで、公開は手動。

## 反証テスト
- 実Run #7の3理由セット + approved lane + safe evidence → 追加1回を許可。
- multi-axis単独 → Run406互換で許可。
- dense単独 / non-engineer単独 / final-surface混在 → 不許可。
- HARD / 非Reader / unsafe evidence → 不許可。
- new / article_revalidation / pending_retry → Run360上限維持。
- 追加修復使用後 → 再度の追加修復は禁止。
