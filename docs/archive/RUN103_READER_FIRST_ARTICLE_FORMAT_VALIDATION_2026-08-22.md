# Run 103 Reader-First Article Format Validation — 2026-08-22

## 結論
Run102 Publish Yield PrecisionをSource of Truthとして複製し、品質/事業ロジックを変更せず、公開Ready記事の最終Markdown構造だけをReader-first化した。

## 変更点
- タイトル直下に`30秒でわかるこの記事`を追加。
- `何が出た？ / なぜ重要？ / 結論は？`を既存Gate通過データから0 API抽出。
- 直後に`元情報`として主一次情報・発見経路・公開更新日を表示。
- 詳細な出典は末尾`Sources / Evidence`へ残し、`補助Evidence`を分離。
- Hacker Newsの発見経路重複を解消。
- Reader headerでは内部Decision codeを文脈に関係なく公開禁止。

## 原価 / リスク
- Gemini追加request: 0
- 外部API追加: 0
- Quality Gate変更: 0
- Notion Schema変更: 0
- Evidence判定変更: 0
- Deep Dive ranking変更: 0

## 専用回帰条件
1. 3項目要約がWhat/Why/最終判断を再利用する。
2. 要約は先頭の完結文だけを採用し、新しいClaimを作らない。
3. `TRY/WATCH/NOW/WAIT/AVOID`が冒頭へ漏れない。
4. `30秒でわかるこの記事`と`元情報`がHuman Editorial本文より前にある。
5. `Sources / Evidence`が本文・判断より後ろに残る。
6. 不明日付は推測せず非表示。
7. HN Discovery表記が権利注記で重複しない。
8. 既存free manuscript/paywall除去仕様を維持する。

## 最終検証
- Run103専用Reader-firstテスト: 8 / 8 PASS
- unittest discover: 432 / 432 PASS
- pytest: 432 passed + 10 subtests passed
- Synthetic Regression Full: 500 / 500 PASS
- Critical failures: 0
- Production write isolation: true
- Python compileall: PASS
- GitHub Actions workflow YAML: 5 / 5 PASS

Run102のQuality Gate / Evidence / Notion / Subscription Attribution / Publish Yieldロジックを維持したまま、公開Ready稿の組み立て層だけにReader-first headerを追加した。
