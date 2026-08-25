# Run120 Japanese Display Label — Final Validation (Run119 baseline)

## 結論
Run119 Evidence Entity Binding Gate完成版へPatchKitを適用し、Run120を完成版として統合した。表示ラベルはIdentity/Evidence/History/launch readinessから分離した任意UI metadataであり、追加Gemini requestはない。

## 実装
- Product Review structured outputに任意 `japanese_display_label` を追加。
- 0 API local normalizerで日本語文字を必須化、80文字超・改行・推奨/誇張/Score/Adoption Status表現をSoft Drop。
- Unknown structured fieldは従来どおりFail-Closed。
- Technology Intelligence / Subscriber Technologyへ `Japanese Display Label` rich_textをFeature Flag有効時のみ書込。
- 既存ラベルは将来model outputが空でも保持。
- Decision History / `_diff_assessment` / Entity ID / dedupe / Evidence Authority / Entity Bindingは不変。
- 0-Gemini idempotent schema migration workflowを追加。
- Feature Flag `ENABLE_JAPANESE_DISPLAY_LABEL=false` default。

## Run119実基準の検証
- Run120 dedicated: 11/11 PASS
- full unittest: 584/584 PASS
- pytest: 584 passed + 19 subtests PASS
- Synthetic Full: 500/500 PASS
- Synthetic critical failures: 0
- Production writes: disabled / isolation maintained
- compileall: PASS
- workflow YAML parse: PASS
- production `_generate_via_chat(` call sites: 7 (unchanged)
- production `genai.Client` sites: 2 (unchanged)

## Mutation Negative Control
3/3 KILLED:
1. optional labelをrequiredへ変更 → dedicated testが検出
2. 推奨・マーケティング表現を許可 → dedicated testが検出
3. Subscriber Entity IDをdisplay labelで汚染 → dedicated testが検出

詳細は `RUN120_MUTATION_NEGATIVE_CONTROL_2026-08-24.log`。

## 運用判断
- Separate translation API: 不採用（quota/粗利悪化）
- canonical name上書き: 不採用（identity汚染）
- bulk Gemini backfill: 不採用（ローンチ前quota消費）
- optional field piggyback: 採用

## 本番証明の境界
この検証はローカル/反証/回帰であり、Notion本番schema migration自体は未実行。本番では `Japanese Display Label Migration` 成功後にFeature Flagをtrueへ切り替える。
