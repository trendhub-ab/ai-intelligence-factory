# AI Intelligence Factory Run408 仕様追補

## 目的
2026-09-13の承認済みRubyGems実記事 Run399 #10 で、初稿は Gemini 3.8 Flash により HTTP 200、Publication Readiness PASS、Human Appeal ACCEPTABLEまで到達した。その後 `FACT_UNSUPPORTED_CLAIM` の局所Quality Retryに入り、3.7はprovider HTTP 503、3.6はPersistent Safety Counterの18/18上限によりprovider送信前に停止した。しかし3.5は1/18しか使用していないにもかかわらず呼ばれず、記事はPending Retryへ戻った。

原因はRun260/278のQuality Retryルーティングにある。Run260は一つのQuality Retryが4モデルへ扇状に広がることを防ぐため、Quality poolを設定上の先頭2モデルへ先に切っていた。現在のquality-first順は 3.7 → 3.6 → 3.5 → 3.8 なので、3.6がPersistent Counterでprovider送信前に拒否されても、3.5は既に候補pool外となる。つまり「provider-visible 2試行を抑える」という本来の意図と「設定上2モデルに切る」という実装が、送信前Safety Capと組み合わさったときだけ不一致になる。

## Run408の変更
通常ProductionのRun260契約は変更しない。`candidate_origin=approved_article_apply` かつ model-based quality/reader repair のときだけ、Run260のquality-first順を維持した全Production poolを、既存のprovider-resilience/budget層へ渡す。

これにより、実Run #10と同じ条件では次のように進む。
1. 3.7: providerへ送信し503。
2. 3.6: Persistent Safety Capで送信前拒否。ローカルDeep Dive枠を消費しない。
3. 3.5: 既存予算に余力があれば次の候補としてprovider送信可能。

Run408自身はAPIを追加で許可しない。実送信の可否・回数は従来どおりPersistent Counter、Deep Dive per-run budget、Gemini local budget、provider circuitが決定する。

## 不変条件
- `ARTICLE_REVALIDATION_REQUEST_BUDGET=5` は変更しない。
- `GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET=5` は変更しない。
- 各モデルのDaily Safety Budget 18は変更しない。
- Fact / Evidence / Publication / Human Appeal / Reader Gateを緩和しない。
- 通常Daily、通常article_validation、通常pending_retryはRun260の既存Quality Retry上限を維持する。
- 初稿Deep Diveのルーティングは変更しない。
- Xロジックは変更しない。
- note.com公開契約は変更しない。今回の到達点はprivate draftまでで、公開は手動。

## Fail-Closed
- approved lane以外ではRun408は元の`_call_deep_dive_pool`へ完全委譲する。
- Quality/Reader repair以外でも元の経路へ完全委譲する。
- Provider routing contractが見つからなければインストール時に停止する。
- 全Production poolを渡しても、既存Budgetが尽きればその場で停止する。
- Gate不合格ならReadyへ進めない。

## 反証テスト
- approved quality retryで 3.7 provider failure → 3.6 pre-send cap → 3.5 success を再現し、3.5へ到達すること。
- provider-visible試行はこの再現条件では3.7と3.5の2回だけであること。
- normal `new` quality retryは既存Run260 routeへ委譲すること。
- approved initial Deep Diveは既存routeへ委譲すること。
- installは冪等であること。
- provider contract欠落時はFail-Closedすること。
