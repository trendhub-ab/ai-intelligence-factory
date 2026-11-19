# AGENTS.md — AIIF / Production

**最優先：本repoで開発・修正・レビューを始める前に、必ず [docs/AIIF_BUSINESS_NORTH_STAR.md](docs/AIIF_BUSINESS_NORTH_STAR.md) を全文読み、事業目的と現行コードの関係を確認する。**

続けて次を読む（内容を推測しない）:
1. [PAID_PRODUCT_CONTRACT.md](PAID_PRODUCT_CONTRACT.md) — 有料商品の現行Source of Truth（Run307）
2. [V1_RETIRED.md](V1_RETIRED.md) — 旧系の停止・許可範囲
3. [NOTION_ACCESS_POLICY.md](NOTION_ACCESS_POLICY.md) — Notionの権限・監査・実行方式
4. 対象機能固有の仕様書・最近のmainコミット。AIIF Nextの実装では [NextのCANONICAL_ARCHITECTURE.md](https://github.com/trendhub-ab/ai-intelligence-factory-next/blob/main/docs/CANONICAL_ARCHITECTURE.md) と DEVELOPMENT_CONTRACT.md を追加で読む。

**本事業はニュース量やCI件数を売らない。** 無料noteで信頼と読者を得て、有料のUse-Decision Intelligence（会員ホーム／Decision Brief／判断DB／Action Asset）へ誘導し、実有料顧客10人から継続価値と収益を検証する。

**開発時の必須行動**
- 既存の収集・Writer・Evidence・Fact・Notion・アイキャッチ・note配送・会員機能を調べ、重複実装を避ける。
- PRでは `.github/PULL_REQUEST_TEMPLATE.md` の6つの事業レビュー項目を埋め、**未接続のE2E区間**も明記する。
- 既存資料を上書き・再定義して正本を二重化しない。事業方針変更はオーナー承認の専用PRでのみ行う。
- 旧V1を復活させず、Nextへ旧Productionの権限・Secretsを暗黙に継承しない。公開はhuman-only。下書きは自動化可能だが保存実物を照合する。
- API予算・コスト・事実・著作権・機密情報の安全契約を維持。CI GREENを実ユーザーの成果と混同しない。
- **`main`へのマージ、ライブ実行、公開、破壊的変更はそれぞれオーナーの明示GOまで行わない。**

これらは人・AIエージェント・レビュー担当の全てに適用する。ブランチへの試験実装は可能だが、完成の基準は単体動作でなく**無料集客→会員価値→継続収益**への貢献と実環境証拠である。
