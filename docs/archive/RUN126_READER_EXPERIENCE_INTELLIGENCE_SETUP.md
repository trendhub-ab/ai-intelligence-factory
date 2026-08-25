# Run126 Reader Experience Intelligence Setup

## Deployment
1. Run126 ZIPの内容をmainへ反映する。
2. 新しいSecret / Variable / Notion Propertyは不要。
3. Synthetic Regression Suite `full` を実行する。
4. Gemini quotaに余裕がある日にReal Article Regression Testを実行する。

## Operational policy
- Reader Experience項目はArticle Audit Artifact内のsoft診断。
- Accessibility / Enjoyment不足だけでHARD FAILしない。
- 比喩・ユーモア・会話調は必須ではない。
- 既存Fact/Evidence/Decision Gateを優先する。
- 本番記事の監査結果が蓄積するまでNotion DBへReader Experience Propertyを追加しない。
