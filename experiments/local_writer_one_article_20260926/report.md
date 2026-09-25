# Local Writer 1記事検証 — 2026-09-26

## 目的

Gemini / OpenAI / その他の外部生成AI APIを使わず、AIIFがすでに保持している構造化された Evidence / Decision / Action だけから、Local Skills相当の編集ルールと純Python処理でnote記事を1本生成できるかを検証する。

これはProduction実装ではなく、1記事だけの反証実験である。

## 基準

- base main: `06d4f81195cf38cb5cf49c3f92538b4a38f17827`
- branch: `experiment/local-writer-one-article-20260926`
- 対象: `arxiv:2608.27364`
- 記事: `Sophistication in GenAI Use: Field Evidence from a Large Firm`

## 入力境界

入力はAIIF内に保存済みの構造化フィールドだけに固定した。

- Source Summary
- What
- Why Important
- Decision / Decision Score
- Decision Reason
- Action
- Primary Risk
- Best For / Avoid For
- Evidence Confidence / Production Readiness
- Evidence URLs
- 保存済みReader Title

既存記事本文は入力禁止。Writerは `note_draft` / `existing_article` / `article_body` 等の本文フィールドを受け付けると失敗する。

## 実行境界

`local_writer.py` はPython標準ライブラリだけを使う。

- Gemini API: 0
- OpenAI API: 0
- その他LLM API: 0
- 外部HTTP取得: 0
- Notion write: 0
- note publish/write: 0
- Production status変更: 0
- main変更: 0

Notionは実験用snapshotを確定するための読み取りにのみ使用した。生成時には参照しない。

## 生成方式

固定テンプレートへの単純なフィールド流し込みだけではなく、以下を純Pythonで行う。

1. 入力schemaと必須フィールドをfail-closedで検証。
2. 既存記事本文の混入を拒否。
3. 内部Decisionコードを読者向け表現へ変換。
4. Evidence / Decision / Action / Riskを、読者が追える順序へ再配置。
5. 既存Evidenceにない数値・固有名詞・比較対象・体験・因果を追加しない。
6. Evidence URLを記事末尾へ保持。
7. 現行Pipelineのparsed Writer payloadと互換なdictへ変換し、zero-provider Gate検証へ渡せるようにする。

## 出力

生成結果は `result_article.md` に固定した。

自動テストでは次を検証する。

- 同じsnapshotから毎回byte-identicalな記事を生成する。
- checked-in結果と実生成結果が一致する。
- 既存記事本文を入力できない。
- 外部通信・provider依存のimportが存在しない。
- Structured Evidence / Decision / Action / Riskが記事に保持される。
- 入力にない数値を増やさない。
- note長文として1,200 visible chars以上、見出し3個以上を持つ。
- reader-facing本文へ内部Decisionコードを漏らさない。
- 現行 Fact / Editorial / Publication / Human Appeal Gate を外部通信なしで実行する。

## CI / Gate 実測結果

Draft PR #529 で既存CIを実行し、3 workflowすべてSUCCESS。

- Notion Access Policy Guard: SUCCESS
- Repository-wide Falsification Guard: SUCCESS
- Integration Reconciliation CI: SUCCESS
- full deterministic regression: 2,922 passed / 1 warning / 0 failed
- Production synthetic smoke: 30 / 30 passed, critical failures 0, production write isolation true

Local Writer固有テストも上記2,922件に含まれ、次のassertionをすべて通過した。

- Fact Gate: PASS / failure 0
- Editorial Gate: PASS / blocking warning 0
- Publication Readiness Gate: PASS / issue 0
- Human Appeal Gate: ACCEPTABLE / issue 0
- checked-in articleとpure Python再生成結果: byte-identical
- reader-facing内部Decision code leak: 0
- 入力に存在しない数値追加: 0
- 既存記事本文入力: fail-closedで拒否
- 本文: 1,301 visible chars
- H2見出し: 4
- Evidence URL: 3本保持

## 最終判定

**この1記事については成功。**

AIIFがすでに保持しているStructured Evidence / Decision / Action / Riskが十分に揃っていれば、外部生成AI APIを使わず、純PythonのLocal Writerだけで、現行Fact / Editorial / Publication / Human Appeal Gateを通るnote記事を生成できることを実証した。

これは「既存記事を手直しした」結果ではない。既存記事本文は入力経路そのものを禁止し、構造化データから再構成した。

ただし、この1件だけで全トピックへの一般化は証明しない。Evidenceが薄い案件、複数論点が競合する案件、記事固有の意外性をルールだけで抽出しにくい案件は別途検証が必要。

したがって現段階の意味は、**Gemini依存をゼロにできる可能性が机上論ではなくなった**こと。全面実装ではなく、次は性質の異なる少数記事で再現率を測る段階である。
