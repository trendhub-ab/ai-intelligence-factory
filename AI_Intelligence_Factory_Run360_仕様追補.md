# AI Intelligence Factory Run360 仕様追補

## 目的

Gemini Production経路のretry責任をFactory側へ一本化し、google-genai SDK内部retryとFactory独自retry/fallbackが重なることで、1つの論理リクエストが多数のProvider-visible HTTP試行へ増幅する状態を解消する。

## 変更前

- google-genai SDKは一時HTTPエラーに対する内部retryを持つ。
- Factoryも503について同一モデル確認retry、model fallback、run-local circuit breakerを持つ。
- この二重化により、Factory監査上の1回の `_generate_via_chat()` が複数のHTTP試行を内包し得る。
- その結果、実Provider負荷とFactory側の利用監査に乖離が生じ得る。

## Run360契約

1. Production Gemini clientは `http_options={"retry_options": {"attempts": 1}}` で再構築する。
2. `attempts=1` は初回送信を含む総試行数1回であり、SDK内部retryを0回にする。
3. retry/fallbackの責任者はFactoryのみとする。
4. 既存の以下は変更しない。
   - 503同一モデル確認retry
   - 10〜20秒の確認delay
   - Pending Retry専用budget保護
   - model fallback
   - run-local circuit breaker
   - RPD/RPM/TPM安全弁
   - Deep Dive / Product Review budget
   - Run260 model routing
   - Fact / Evidence / Editorial / Human Appeal / Publication gate
   - Notion永続化
   - Groq provider line
5. Production runtimeでAPI keyが存在するのにsingle-owner clientを構築できない場合はFail-Closedとする。
6. offline/synthetic testでAPI keyが存在しない場合はProvider clientを生成せず、network side effectを発生させない。
7. installはidempotentとし、二重installでclient再構築やretry層を重ねない。

## Rollback authority

Run360導入直前のGemini-only Production状態を以下に保存する。

- branch: `backup/gemini-only-run359-20260912`
- commit: `41b077ab9c26dd0307eb6c11feeeea6163d35441`

Run360以降のProvider改修で重大な回帰が確認された場合、このbranchを比較・復旧の基準とする。バックアップbranch自体には改修を加えない。

## 検証

PR #285で以下を確認済み。

- Notion Access Policy Guard: SUCCESS
- Repository-wide Falsification Guard: SUCCESS
- Integration Reconciliation CI: SUCCESS
- full deterministic regression: SUCCESS
- current Production stack synthetic smoke: SUCCESS

追加回帰 `test_run360_gemini_retry_owner.py` では以下を固定する。

- SDK total attempts = 1
- Factory retry owner marker = `factory`
- install idempotency
- no-key offline pathでProvider clientを生成しない

## 次のlive検証

Production Dailyを直ちにフル実行するのではなく、保存済み候補を使ったbounded Gemini validationで以下を観測する。

1. 1回のFactory attemptにつきProvider-visible SDK attemptが1回であること。
2. 503発生時、Factory logが503を直接認識し、独自delay/fallbackへ移ること。
3. 同一候補の503連鎖回数がRun359以前より縮小すること。
4. 429/RPD/TPM判定、Persistent counter、Deep Dive budgetが従来どおりFail-Closedであること。
5. 生成品質・監査結果・Notion persistenceに差分がないこと。

live検証が失敗した場合はProduction Dailyへ展開しない。
