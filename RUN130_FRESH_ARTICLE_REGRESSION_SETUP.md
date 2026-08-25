# Run130 Fresh Article Regression Setup

## 目的
Real Article Regression Testを、従来の固定A/B比較用3記事だけでなく、実行時点で新規取得した候補3件でも検証できるようにする。

## Workflow UI
GitHub Actions > Real Article Regression Test > Run workflow で `article_set` を選択する。

- `fixed`: 従来互換。Notionに保存済みの既存Deep Diveを再生成し、Run間のA/B比較に使う。
- `fresh`: 新規候補を各ソースから取得し、既存Notion URLを除外して3件を生成する。本番耐性・未知テーマ適応力の確認に使う。

## fresh の安全設計
- Gemini Screening APIは使用しない。
- GitHub / Hacker News / arXiv / Product Huntの通常取得関数を、1ソース最大12件の小さい範囲で利用する。
- Productionと同じLegal Safety Gateを適用する。
- Notion既存URLをREAD ONLYで取得し、既知記事を除外する。重複チェックが失敗した場合はFail-Closed停止する。
- 候補選定は一次情報の取得しやすさ・source-native engagement等のメタデータだけで行う0-API選定であり、Production Decision Scoreではない。
- Notion create/update、Stock保存、Screening、アイキャッチupload、公開処理は行わない。
- 選ばれた記事だけ、既存のDeep Dive + Quality Gateを `persist_results=False` で通す。

## APIコスト
`fresh` 追加によるGemini候補選定コールは0。Gemini消費は従来Real Article Regressionと同様、選択された記事のDeep Dive/Quality Retryに限定される。

## 推奨運用
- prompt差分を厳密比較したい場合: `fixed`
- 新しいテーマで一般化性能を確認したい場合: `fresh`
- Run129 Conversational Warmthの採用判定: `fresh` を推奨
