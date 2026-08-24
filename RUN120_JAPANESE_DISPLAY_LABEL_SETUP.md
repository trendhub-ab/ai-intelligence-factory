# Run120 Japanese Display Label — Setup

## 目的
`Technology / Project Name` をIdentityの正本として維持したまま、Technology Intelligence / Subscriber Technologyに任意の日本語表示ラベルを追加する。別Gemini requestは追加しない。

## 本番導入順
1. Run120完成版をmainへ反映する。
2. GitHub Actions `Japanese Display Label Migration` を1回実行する。
3. 出力でTechnology Intelligence / Subscriber Technologyの `Japanese Display Label` が追加済みまたは既存であること、`zero_gemini_calls=true`を確認する。
4. Repository Variable `ENABLE_JAPANESE_DISPLAY_LABEL=true` を設定する。
5. 通常のProduct Review / Subscriber Inventory Bootstrapを再開する。

## 重要な不変条件
- `Technology / Project Name`、Canonical Entity ID、Primary URL、Entity Aliasesは変更しない。
- `Japanese Display Label` はUI専用・任意。欠落/不正でもProduct Reviewを失敗させない。
- Decision History / meaningful change / launch readiness / Evidence Authority / Entity Bindingには使用しない。
- 既存レコードのGemini一括翻訳は行わない。今後の通常Product Review / Re-reviewで自然充足する。
- Feature Flagはmigration成功前にtrueへしない。
