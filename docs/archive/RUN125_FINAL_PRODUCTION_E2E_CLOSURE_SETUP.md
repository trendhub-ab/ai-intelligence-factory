# Run125 Final Production E2E Closure — Setup

## 目的
Run124のReal Article Regression実稿で残った3つのFalse Positiveを、追加Gemini APIなしで局所修正する。

## 追加設定
- Notion DB schema変更: なし
- GitHub Secrets追加: なし
- GitHub Variables追加: なし
- Gemini call site追加: なし

## 導入手順
1. Run125完成版を`main`へ反映する。
2. 必要ならSynthetic Regression Suite = `full`を実行する。完成版ローカルでは500/500 PASS済み。
3. Gemini API枠が利用可能な時に`Real Article Regression Test`を`main`で1回実行する。
4. Artifactの3記事についてAccept/Reject理由と最終稿を監査する。
5. 特にMCP稿で以下が再発していないことを確認する。
   - `unsupported numeric claim: 1リクエスト`
   - `source-boundary unsupported named fact: JSON Schema`
   - `monotonous sentence endings`のFalse Positive
6. 真の数値上限、未知製品名、実際の同一文末連打が引き続き止まることも確認する。

## 運用方針
Run125で新しい機能やDBは増やさない。Real Article Regressionが妥当なら記事品質ロジックを凍結し、以後は実記事で再現する具体的欠陥だけを修正対象とする。
