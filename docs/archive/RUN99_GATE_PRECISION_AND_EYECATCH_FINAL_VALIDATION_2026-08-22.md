# Run 99 Gate Precision + Eyecatch Final Validation — 2026-08-22

## Purpose
Run 99本番でReady 0となった原因を、Quality Gateを弱めて見逃しを増やすのではなく、False Positive / False Negativeの双方を反証して修正する。同時に、ユーザー確定のEyecatch最終デザイン（余白・上下中央・Lato Bold数字）をコードへ正式統合する。

## Root cause confirmed from Run 99
- Screening JSON破損対策、Multilingual Title、Rescue Loss Limit、Gate Funnelは本番で正常動作。
- Ready 0の主因はFact Relation Gateの過剰検出。
- 旧Relation Gateは日本語の裸の名詞「開発」もrelation predicateとして扱い、`開発体制 / 開発進行 / 開発環境`と技術名の列挙をactor→object関係に誤変換していた。
- `coverage.benchmark=FOUND`も、単にbenchmark語が存在するだけで「ベンチマーク結果がない」という記事文をFalse Negative扱いできる余地があった。
- HN外部URLが取得できた場合、Reuters等の二次報道までPrimary Authorityとして扱う余地があった。
- Quality Retryが内部管理コード`WATCH`等をARTICLEへ再導入するケースがあった。

## Implemented corrections

### 1. Fact Relation Gate — precision-first hard gate
Hard Fail対象を「主体＋関係動詞＋対象が文法的に明示された関係主張」に限定。

Hard Failを維持する例:
- `Timescale社がpgvectorを提供しています。`
- `Karpathy氏がAgentMemoryを提唱しました。`
- `Acme provides WidgetX.`（Evidenceに同じ関係がなければFail）

Hard Failしない例:
- `OpenTelemetryの開発体制ではCore、Python、Rubyの状況を確認する。`
- `Forgejo、Coolify、Postgres、Redisを組み合わせた開発環境を検証する。`

日本語の`開発/提案/採用/提供`という裸の名詞はrelation triggerにしない。明示的な動詞活用だけを認識する。

### 2. False Negative Evidence — substantive evidence requirement
`coverage=FOUND`だけでは反証しない。
- benchmark: benchmark/evaluation/result周辺に具体的な性能値・条件・比較結果がある場合のみsubstantive。
- runtime: 時間単位付き具体値を要求。
- hardware: GPU/CPU/H100/A100等の具体記述を要求。
- code availability: GitHub/repository/source code等の具体記述を要求。

これにより「benchmarkという語を論じているだけ」の原資料を、benchmark結果ありと誤認しない。

### 3. Primary Source Authority — secondary news is not primary
HN / Product HuntはDiscovery Source。
- Reuters/AP/Bloomberg/TechCrunch/The Verge/Wired/Ars/CNBC等の二次報道は、取得成功しても製品・ベンダー主張のPrimary Authorityにはしない。
- ベンダー価格・仕様・リリースの評価は公式発表/Docs/GitHub等へ解決できなければFail-Closed。
- 一方、Dan Luu等の著者本人の技術ブログは、その著者自身の実験・意見のPrimary Sourceとして許可。

### 4. Internal Decision Code leak hardening
- Quality Retry instructionへ`NOW / TRY / WATCH / WAIT / AVOID`をARTICLEへ出さない制約を再注入。
- Gateは`（WATCH）`、`Decision: WATCH`、`WATCH と判断`等のdecision contextのみ検出。
- `Apple Watch`やMarkdown code block内の`WAIT`等は誤検出しない。
- Final Japanese Polishで公開本文中の明示的なmanagement labelだけ0 APIで自然文へ修復。code block / inline codeは変更しない。

### 5. Eyecatch final integration
ユーザー確定デザインをコードへ正式統合。
- 1280x670、Source別背景。
- 左カードの内側余白を拡大。
- Header / Main Score / Bar / sub-score cardsをカード内で光学的に上下中央配置。
- 数値`81/100`, `21/25`, `12/20`等はGoogle Font `Lato Bold`を最優先。
- GitHub Actionsは`fonts-lato`をapt install済み。フォントファイル自体はRepository/ZIPへ同梱しない。
- 進捗バー色は既存正式5段階を維持: Gray/Cyan/Blue/Purple/Gold。
- EligibilityはArticle Ready。Decision Score閾値ではない。

## Counterexample / falsification checks
1. False Positive defense: bare `開発` noun + entity list => Relation Gate PASS.
2. False Negative defense: explicit unsupported Timescale→pgvector => FAIL.
3. False Negative defense: explicit unsupported Karpathy→proposal => FAIL.
4. Supported relation: Acme→WidgetX with same evidence relation => PASS.
5. Benchmark keyword only => no false contradiction.
6. Concrete `48 ms at 10 RPS on H100` evidence + “benchmark未確認” => contradiction detected.
7. `WATCH` decision label => leak detected/repaired.
8. `Apple Watch` => no leak.
9. Reuters via HN => Primary Authority insufficient.
10. Author-original Dan Luu blog via HN => Primary Authority accepted.

## Validation results
- All unittest: **398 / 398 PASS**
- pytest: **398 passed + 10 subtests PASS**
- Synthetic Regression Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Production write isolation: **true**
- Python compile: **PASS**
- Workflow YAML: **PASS**
- Eyecatch final render: **1280x670 PASS**
- `decision_intelligence.py`: unchanged from baseline
- `migrate_decision_intelligence.py`: unchanged from baseline
- `requirements.txt`: unchanged from baseline

## Live acceptance criteria for Run 100
- Relation Failがentity列挙/`開発体制`等では発火しない。
- 明示的なactor→relation→object誤帰属は引き続きFailする。
- `Dynamic Retry Attempted`がRelation False Positiveだけで増えない。
- Ready > 0を品質緩和なしで回復できるか確認する（Evidenceが本当に弱い日は0を許容）。
- Ready記事が出た場合、最終Eyecatch（Lato Bold数字、余白/中央配置、Score Color）が生成される。
