# Run224 — Multiplier Deterministic Rescue

## 目的

Run223が`performance_multiplier_scope_lost`を正しくHARD検出した後、同じClaimを直すためだけにGemini Quality Retryを消費して503・再ハルシネーションへ入る経路を減らす。

## Production contract

`run224_multiplier_deterministic_rescue.py`は既存の`_apply_deterministic_publication_rescue`をzero-modelで拡張する。

- Run223の`performance_multiplier_scope_lost`診断がreason rowsに存在する場合だけ発火する。
- `x倍`/`x faster`等の性能倍率がある本文文だけを対象にする。
- 元の倍率・数値・Evidence・Decision・Score・URLは変更しない。
- 数値保存チェックはUnicodeの`\w`境界に依存せず、日本語の直後にある`1.9倍`や識別子内の数字も含むnumeric lexeme列を前後比較する。1つでも変化すればRun224 rescue自体を破棄してfail-closedとする。
- 対象文の直後へ、一次情報に基づく条件付きの目安であることと、実際の改善幅が処理内容・条件・実行環境で変動することだけを追記する。
- Markdown headingとfenced codeは編集しない。
- 既にscope/variabilityがある場合は何もしない。再実行しても二重追記しない。
- 既存のsubtractive rescue（unsupported hype等）は先に実行し、その結果を保持する。
- `_rescue_loss`の削除数・numeric removal判定を増やさない。
- Gemini/model callは0。
- Rescue後は通常のFact / Editorial / Publication / Human Appeal Gateを再通過しなければReadyにしない。

## 背景となった実測

2026-09-04のGPT-6 Astra Pending Retryでは、Deep Dive生成後にRun223が性能倍率のscope lossを検出した。Quality Retryは3.6 Flashで503、3.7 Flashでは成功したが、最終稿にも同じscope lossが残りQuality Failedとなった。

この障害から、検出器ではなく「検出後の局所救済」が欠けていると判断した。Run224は品質Gateを弱めず、追加APIを使わず、その狭い欠落だけを補う。

## 反証で追加した防御

PR #95のfull unittestで、旧numeric testに使った`(?<![\w.])`が`性能が1.9倍`の`1.9`を拾えないことが判明した。PythonのUnicode regexでは日本語のかな・漢字も`\w`に含まれるためである。

これは単なるテスト期待値のミスだけではなく、同じ境界を使っていたRun224のnumeric preservation guardが日本語隣接数値に対して盲点を持つことも意味した。そこで、数値抽出をUnicode word-boundary非依存のnumeric lexeme比較へ変更し、さらに`1.9→2.0`を故意に注入した場合にrescue全体を破棄する反証テストを追加した。

## 非目標

- 根拠のない主体名・ベンチマーク名・条件値を生成しない。
- 数値を推測・補正しない。
- Human Appealやdense reportを理由にEvidenceを削らない。
- Fact/Evidence不足そのものをRescueしない。
- Public note releaseを行わない。
