# AI Intelligence Factory Run406 仕様追補

## 目的
Run405の実記事検証では、Publication ReadinessはPASSし、Reader失敗は `multi_axis_reader_weakness` のみに縮小した。一方、専用Run399の5リクエスト枠のうち4枠しか使っておらず、Run360の「Reader Repairは1回まで」契約によって最後の1枠が未使用のままEditorial Reviewへ停止した。

Run406は通常ProductionのRun360契約を変えず、オーナーが明示承認したRubyGems 1記事のRun399 laneだけで、Reader-only残存時に追加1回のReader Repairを許可する。

## 適用条件
追加修復は次をすべて満たす場合だけ許可する。
- candidate_origin が `approved_article_apply`。
- 既存retry policyが `run360_reader_repair_already_spent` を返した後である。
- Evidence state が `SUFFICIENT`。
- `decision_scope_safe == true`。
- blocking rowsがすべてReader Value系で、HARDを含まない。
- 残存理由が実Run405で再現した `multi_axis_reader_weakness` だけである。
- Run406の追加修復をまだ使っていない。

## 上限
- Run406追加修復は最大1回。
- 3回目のReader Repairは禁止。
- `ARTICLE_REVALIDATION_REQUEST_BUDGET=5` と `GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET=5` は変更しない。
- Provider側で残予算がなければFail-Closed。

## 非変更領域
- 通常Daily / article_validation / pending retryのRun360上限。
- Fact / Evidence / Publication / Reader Gateの閾値。
- Decision Score、Evidence、数値、重要制約。
- Gemini 503 fallback / daily persistent budget。
- Notion Ready閾値。
- note公開契約。今回の到達点はprivate draftまでで、公開は手動。
- Xロジック。

## 再判定
追加Reader Repair後もFact / Evidence / Publication / Reader Gateをすべて再実行する。1つでも不合格ならReadyへ進めずEditorial Reviewのまま停止する。

## 反証テスト
- approved lane + safe evidence + residual multi-axisだけ → 追加1回を許可。
- 同じ条件の2回目 → `run406_second_reader_repair_already_spent` で拒否。
- new / article_revalidation / pending_retry → Run360上限を維持。
- HARD / 非Reader / dense-only / unsafe evidence → 追加修復禁止。
