# Run 98 Quality Hardening Validation — 2026-08-22

## Purpose
Run 98の実運用で判明した記事公開品質・API効率・計測整合性の問題を、Free Article Reliability / Revenue Product Phase 2を壊さず修正する。

## Implemented changes

1. Screening JSON Reliability
   - `SCREENING_BATCH_MAX_OUTPUT_TOKENS` 既定値/Workflow値を 2500 → 5000。
   - HTTP 200でもJSON配列末尾が切れた場合、balancedな完全JSON objectだけを0 APIでsalvage。
   - 未完・壊れたobjectは推測修復せず、欠損IDのみ既存Recoveryへ送る。

2. Publication Rescue Loss Limit
   - 削除文数を監査。
   - 3文以上削除、またはFact Numeric mismatchに起因する重要数値文の削除が発生した場合、Deterministic Rescueだけでは自動Readyにしない。
   - 初回Gateであれば既存のDynamic Quality Retry 1回へ送り、文章価値を再構成する。

3. Gate Funnel Consistency
   - `retry_succeeded` は `retry_attempted=true` の場合のみ成立。
   - Deterministic RescueだけでReadyになった記事をDynamic Retry Successへ誤計上しない。
   - Final Rescue失敗時はrescued稿を再評価した最新Gate診断へ更新し、削除済みFact Errorを最終Failure理由へ残さない。

4. Eyecatch Eligibility
   - Decision Score閾値によるskipを廃止。
   - Article publication gateを通過したReady candidateを基本条件とする。
   - Decision Scoreは色表現には利用してよいが、画像生成可否には使わない。

5. Fact Relation Gate
   - EntityとEntity/概念の関係主張（提供・提唱/提案・採用・開発）をdeterministicに監査。
   - EntityがEvidence内に別々に存在するだけではPASSしない。同一Evidence sentence内にActor + Relation（2 Entityがある場合は双方）を要求。

6. Primary Source Authority Gate
   - Product Hunt / Hacker NewsはDiscovery Sourceとして扱う。
   - 製品/技術評価では公式サイト・Docs・GitHub・論文等へ解決され、実取得できたPrimary URLを要求。
   - Product Hunt metadataだけでは`primary_source_resolved`にしない。
   - Product Hunt記事末尾の「原資料URL」は解決済みPrimary URLを使用し、PH URLは発見経路として分離。

7. Template Diversity
   - 5 styleを安定hash rotation: problem / experiment / numbers / surprise / comparison。
   - 過去見出しはparser/gateのbackward compatibility aliasとして維持。

8. Final Japanese Polish
   - 0 API deterministic cleanupをGate前に実行。
   - `性能をな低コスト`、重複phrase等の明確な機械破綻を安全な範囲で修正。
   - 未修復の怪しい助詞列等はEditorial warningへ残す。

## Validation
- Dedicated free article tests: 30/30 PASS (Run 98追加Regressionを含む)
- All unittest: 375/375 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Production write isolation: true
- Python compile: PASS
- Workflow YAML: 5/5 PASS
- `migrate_decision_intelligence.py`: unchanged
- `decision_intelligence.py`: unchanged
- `requirements.txt`: unchanged

## Live acceptance criteria for next Daily
1. Screening JSON decode error時に `salvaged=N` が記録され、全25件を丸ごとRecoveryしないこと。
2. `Dynamic Retry Success <= Dynamic Retry Attempted` が常に成立すること。
3. 3文以上/重要数値削除時に `[RESCUE LOSS LIMIT]` が出てDeterministic RescueのみでReady化しないこと。
4. Decision Score < 60でもQuality Gate PASS記事はEyecatch生成対象になること。
5. Product Hunt由来の記事は公式Primary URLが解決できない場合Fail-Closedすること。
6. Ready記事本文に5 styleの多様性が現れ、固定見出し反復が減ること。
