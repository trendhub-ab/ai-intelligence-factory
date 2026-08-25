# Run131 Validation — 2026-08-25

## 結果
- Run131専用 unittest: 7/7 PASS
- 全 unittest: 680/680 PASS
- pytest: 680 passed + 19 subtests PASS
- compileall: PASS
- Synthetic Regression harness self-test: PASS
- Synthetic Full: 500/500 PASS
- Critical failures: 0
- Production write isolation: true
- `_generate_via_chat(` call sites: 7（増加なし）
- `genai.Client(`: 1（増加なし）
- Notion schema変更: 0

## 反証したポイント
1. 親近感を増やすほど本文が肥大化する
   - 対策: 会話文/日常例は追加ではなく既存の硬い説明を置換。
2. 文字数上限でEvidence/Decisionが薄くなる
   - 対策: 専門概念を2〜4個へ編集選択。削減対象を重複・不要内部実装へ限定。
3. 比喩や雑談が新しいFactを生み、Rejected率を上げる
   - 対策: 親近感表現から新規固有名詞・数値・市場Claimを作らない。
4. 「ですよね」を必須にするとAIテンプレ化する
   - 対策: 固定語ではなくReader Proximityという機能を要求。過剰反復監査は維持。
5. WarmthをHard/Review Gate化するとAPI Retry/Rejectが増える
   - 対策: `REVIEW_MISSING` はArticle Auditのsoft-only診断。追加Gemini retryなし。

## Synthetic実行注記
実行コンテナには `google.genai` がないため、Regression Suiteの非API synthetic実行時のみ一時的な外部stubを `PYTHONPATH` に置いた。Repository本体は変更していない。Synthetic SuiteはGemini APIを呼ばず、500/500 PASSを確認した。
