# V2-001 Shadow Selection Vertical Slice — Design Specification

- Status: REVIEW
- Date: 2026-10-13
- Base main: `8cc13a90272733f7f3cd0b53a008717f2bbe8314`
- Scope: AIIF Rebuild V2 / first vertical slice
- Production authority: unchanged (V1)

## 1. Decision

V2-001は、AIIF Rebuild V2の最初の実装単位として、**選定だけをV2で縦に通す shadow-only sidecar** を構築する。

不変条件は次の1行で定義する。

> **V2が選ぶ。V1が書く。**

V2-001ではV2は候補取得・正規化・安価なScreening・上位候補1件のDeep Dive・V1とのshadow比較・構造化レポート出力までを担当する。記事生成、Notion書込み、note配送、公開判定、Economic State更新その他のProduction mutationはV1に残す。

V2の結果はProduction authorityを持たず、V1のDaily/Fresh/既存workflowの結果を変更しない。

## 2. なぜこの切り方か

現行V1は長期運用の結果として `pipeline.py` に多くのProduction責務を持つ。一方、編集オーケストレーションの一部は既に `pipeline.py` 外へ分離され、`deep_dive_portfolio.py` にはprovider-free / zero-modelの候補順序付けsurfaceも存在する。

V2-001で既存V1へ新しい選定ロジックを直接差し込むと、Rebuildの検証中にProduction契約を汚染する。逆に別サービス化すると、現段階ではデプロイ・監視・秘密情報・運用保守の固定費が増え、得られる検証価値に対して高コストである。

したがって、**同一repository内の論理sidecar** とし、V1とコード境界を分けながらインフラは増やさない。

## 3. 検討した3案

### A. 同一repo内の論理sidecar（採用）

V2 selectionを独立module/packageとして構築し、明示的なshadow runnerからだけ呼び出す。

- Production経路を直接変更しない
- V1の既存adapter/helperを必要最小限reuseできる
- 新しい常駐サービスやDBが不要
- 後続sliceでV2 authorityを段階的に上げられる

### B. V1 `pipeline.py` 内にfeature flagでV2選定を追加（不採用）

初期コード量は少ないが、V2検証ロジックとV1 Production責務が再び密結合になる。Rebuildの目的である境界整理に逆行し、flag条件の増殖と回帰リスクを生む。

### C. V2を別service / repositoryとして構築（現時点では不採用）

境界は最も明確だが、deploy、credentials、observability、version coordination、運用保守が増える。V2-001の検証目的には過剰であり、収益化へ寄与しない固定費が先に発生する。

## 4. V2-001のGoal

1回のshadow runで、以下をend-to-endに成立させる。

1. boundedなsource/providerから候補を取得する
2. 候補を共通contractへ正規化し、重複を除く
3. model costを抑えたScreeningで候補を順位付けする
4. Deep Dive対象を**最大1件**に限定する
5. Deep Dive後のV2 winnerを決める、または証拠不足としてwinnerなしにする
6. 同runで参照可能なV1選定結果があればshadow比較する
7. side effectなしの構造化report/metricsを出力する

このvertical sliceの価値は、V2の選定品質をProductionへ影響させず測定できることにある。

## 5. Non-goals

V2-001では以下を実装しない。

- 記事本文・タイトル・CTA・アイキャッチ生成
- Gemini等による公開原稿生成
- Publication Gateの置換
- Notionへのcreate/update
- note draft作成・更新・公開
- Presentation DB / Content Intelligence DB / Technology Intelligence DBのmutation
- Economic Stateのmutation
- V1のDaily/Fresh/Rolling Re-reviewのauthority変更
- V1 selectionの削除
- 複数候補へのDeep Dive
- 新規の常駐service / database / queue
- Rebuild V2全体の一括置換

Economic Stateの詳細契約はV2-001の入力でも出力でも定義しない。既存正本が明示されるまで推測で追加しない。

## 6. Boundary

### V2 owns in this slice

- Acquisition orchestration
- Candidate normalization
- Candidate deduplication
- Cheap Screening
- Selection ranking
- One Deep Dive decision
- V2 selection result
- V1 comparison result
- Shadow report / metrics

### V1 keeps authority

- Production scheduling
- Production persistence
- Article generation
- Editorial retry / quality repair
- Publication readiness
- Eyecatch generation
- Notion canonical writes
- note delivery
- Production economic-state updates

V2 outputをV1のwrite pathへ渡してはならない。

## 7. Data flow

```text
Shadow Runner
    |
    v
Bounded Acquisition
    |
    v
Normalize + Deduplicate
    |
    v
Cheap Screening
    |
    v
Ranked candidates
    |
    +---- no eligible candidate ----> insufficient_evidence report
    |
    v
Top candidate only
    |
    v
Deep Dive (max 1/run)
    |
    +---- insufficient evidence -----> insufficient_evidence report
    |
    v
V2 Winner
    |
    +---- optional V1 reference -----> Shadow Compare
    |
    v
Structured Report / Metrics

NO Production mutation
```

## 8. Candidate contract

V2内部ではprovider固有payloadを下流へ漏らさず、最低限以下の意味を持つnormalized candidateへ変換する。

必須概念:

- stable candidate identity
- source/provider identifier
- primary URL
- title/name
- short description or evidence snippet when available
- source timestamp when available
- acquisition timestamp
- screening score
- screening reasons
- evidence sufficiency state

既存V1のfield名を無条件にV2の正本へコピーしない。V1 adapterはV2 contractへの変換境界として扱う。

## 9. Screening policy

ScreeningはDeep Diveより安価でなければならない。

初回sliceでは次を守る。

- deterministic / provider-freeで判断できる項目を先に使う
- source authority、freshness、candidate completeness、重複、既知の低価値条件などを安価に判定する
- model callをScreeningの必須条件にしない
- candidate数を固定上限でboundedにする
- scoreだけでなくreason code / reason textを残す

既存 `deep_dive_portfolio.py` のようなzero-model helperは、意味が一致する場合だけreuseする。Production persistence前提のhelperをそのままV2 contractにしない。

## 10. Deep Dive budget

V2-001のDeep Diveは**最大1件/run**とする。

- eligible candidateが0件なら0 callで終了
- 1件以上ならScreening最上位の1件だけをDeep Dive対象にする
- Deep Dive失敗時に2位候補へ自動fallbackして追加callしない
- provider errorやevidence不足は構造化failureとして記録する

これにより、selection品質を比較しながらAPI費と実行時間の上限を明確にする。

## 11. Fail-closed behavior

V2が不確実なときはwinnerを作らない。

以下では少なくとも `insufficient_evidence` または明示的なfailure categoryを返す。

- 全providerが取得失敗
- normalization後に候補0件
- Screeningを通過する候補0件
- top candidateのDeep Diveが必要証拠を満たさない
- Deep Dive providerが失敗
- output contractが壊れている

**V2失敗はV1失敗を意味しない。** Shadow sidecarのfailureはProduction workflowを停止・変更しない。

## 12. V1 shadow comparison

V1比較対象は、同runまたは呼び出し側から安全に渡せる「V1が選んだcandidate identity」をread-only referenceとして受ける。

V2-001はV1結果を取得するためにNotion等へ新しいwriteを行わない。

comparison statusは最低限以下を区別する。

- `same` — V1とV2が同一candidate
- `different` — 異なるcandidate
- `v2_no_winner` — V2がwinnerを作らなかった
- `unavailable` — V1 referenceを安全に取得できない

`unavailable` はshadow run自体のfailureにしない。

## 13. Observability contract

1 runごとに、少なくとも以下を機械可読で出力する。

- run id / timestamp
- mode = `shadow`
- provider/sourceごとのsuccess/failure
- acquired candidate count
- normalized candidate count
- deduplicated candidate count
- screened candidate count
- Screeningのscore/reason
- Deep Dive attempted count (`0` or `1`)
- Deep Dive result category
- V2 selected candidate identity（winnerがある場合）
- V1 reference identity（利用可能な場合）
- comparison status
- failure category（失敗時）
- configured candidate/provider/deep-dive budgets
- actual model/provider call count when measurable

ログはsecret、full private manuscript、credential、private Notion contentを出力しない。

## 14. Side-effect contract

V2-001 shadow executionから以下のwrite pathへ到達できてはならない。

- Notion write
- note write/publish
- Production delivery ledger mutation
- Production queue mutation
- article canonical body mutation
- Production status / Ready state mutation

テストでは「呼ばれなかったこと」を明示的に証明する。

## 15. Configuration and rollout

- shadow modeを明示指定しない限りV2 selectionはProduction authorityを持たない
- Production defaultはV1 authorityのまま
- V2-001は専用runner/testから実行可能にする
- 初回段階では既存Daily workflowへ自動接続しない
- Productionへの自動schedule追加は後続sliceで別承認とする

RollbackはV2 shadow invocationを止めるだけで成立し、DB migrationやdata repairを必要としない設計にする。

## 16. Security / privacy

- 新しいsecretを原則追加しない
- 既存provider credentialをreuseする場合もV2 moduleへsecret値を保存しない
- reportにはcredential、private page本文、非公開draft本文を含めない
- network adapterは許可されたsource/provider境界に限定する

## 17. Acceptance criteria

V2-001実装完了には以下をすべて満たす必要がある。

1. V2 selection pathがV1 production writerから論理的に独立している
2. candidate取得からreportまでfixtureでvertical sliceが通る
3. 同一入力でnormalize/dedupe/rankingがdeterministicに再現する
4. Deep Dive attemptがrunあたり0または1である
5. 2位以下へのautomatic Deep Dive fallbackがない
6. provider partial failureを隔離し、残存候補で安全に判断できる
7. evidence不足時はwinnerを捏造せずfail-closedする
8. V1 reference unavailableでもProductionへ影響せずreportを返す
9. success / no-winner / provider-failureの構造化report contractをテストする
10. Notion/note/generation/economic-state等のwrite side effectが0であることをテストする
11. 既存V1 focused tests / full pytest / repository guardsが回帰しない
12. mainへmergeする前にshadow実行結果を人間が確認できる

## 18. Implementation constraints for the next phase

Design承認後のimplementation planでは、以下を優先する。

- 新規V2 logicは独立module/packageへ置く
- `pipeline.py`への変更は0またはadapter露出に必要な最小限にする
- 既存Production functionをmonkey-patchしてV2化しない
- network / model adapterをinterface境界へ隔離しfixtureで置換可能にする
- test-firstでREDを作ってからproduction codeを書く
- 新しい有料provider callを増やす設計を避ける
- 実環境proof前にprovider-free fixture proofを完了する

## 19. Deferred decisions

以下はV2-001では決めない。

- V2がProduction selection authorityを持つ条件
- V2 selectionをDaily/Freshへ接続する時期
- multiple Deep Dive / adaptive budget
- V2側の永続DB
- article generationのV2化
- note deliveryのV2化
- Economic StateのV2 writer
- V1 retiredown計画

これらはV2-001のshadow evidenceを見てから次sliceで判断する。

## 20. Review gate

この文書が承認されるまで、V2-001のproduction codeは書かない。

承認後の順序:

1. implementation plan作成
2. RED tests
3. minimal implementation
4. focused tests
5. full pytest
6. repository guards
7. bounded shadow proof
8. merge readiness review

main mergeは別途明示的なGOを必要とする。
