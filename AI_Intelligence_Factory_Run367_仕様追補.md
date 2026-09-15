# AI Intelligence Factory Run367 仕様追補

## 目的

Daily `full` の候補探索へ X を正式に追加する。ただし X は **Discovery Signal 専用**とし、X投稿本文・投稿者の主張・反応数を Fact/Evidence として昇格させない。

既存の GitHub / HackerNews / ArXiv / OfficialVendor の4系統は引き続きProductionの基幹取得系統とする。Xは5番目の追加探索面であり、X/Apify障害によって既存4系統を停止させてはならない。

## Production契約

1. X取得は `full` のときだけ有効化する。`article_validation` と `pending_retry_validation` はX取得を行わず、Apify資格情報も渡さない。
2. Providerは当面 Apify Actor `simple.actor~x-profile-posts` を使用し、X公式APIは使用しない。
3. 監視対象は `x_discovery/watchlists/ai_core_20.json` の20アカウントに固定する。
4. 1プロフィール最大5投稿、12時間窓、100 records上限、1 runあたり requested charge上限 `$0.05` を超えない。
5. 20プロフィールは1プロフィール単位で隔離取得する。1プロフィールのActorエラー・payload drift・空レスポンスで他プロフィールやDaily全体を停止しない。
6. `t.co` は既存 `x_discovery` resolverで外部URLへ解決する。
7. Factoryへ渡せるのは、既存の保守的primary-source candidate classifierを通り、X内部URL・未解決短縮URLではない外部URLだけとする。
8. X由来candidateの `source` は `X`、`source_role` は `discovery_signal`、`evidence_status` は `discovery_only` とする。
9. `raw_source_not_evidence=true`、`is_evidence=false` を維持する。X投稿本文を `sourceContext` や記事のEvidenceへコピーしない。
10. X由来candidateのFact確認は、Deep Dive以降でリンク先の一次情報を通常ロジックどおり検証して行う。

## Dedup契約

Xから解決したURLは、Screeningへ入る前に既存取得bucketの `url` / `primaryUrl` とcanonical URLで比較する。`utm_*`、`fbclid`、`gclid`等の追跡queryとfragmentだけを除き、意味を持つqueryは保持する。

同一URLが既存4ソースですでに見つかっている場合はX側を捨てる。その後も既存Notion Dedupを通すため、重複防止は二段構えとする。

## Failure semantics

Xは加算系統である。以下はすべて `X DISCOVERY DEGRADED` として明示ログを残し、既存4ソースでDailyを継続する。

- `APIFY_TOKEN` 欠落
- Actor ID不一致
- Actor/HTTP障害
- 個別プロフィール障害
- queue読み込み/変換障害
- X候補0件

X障害を隠して「成功したX取得」と見せかけてはならない。一方、X障害だけを理由にProduction `full` 全体をFAILさせない。

## Cost契約

XはSource ROIによる可変fetch allocationには当面参加させない。理由は、Apify側で20プロフィール分離＋総課金上限という別の外部コスト契約を持つためである。

Run367では固定上限 `$0.05/run` を優先し、Xを増やすためにGemini予算・Deep Dive枠・既存4ソース取得枠を増額しない。Screening総数は既存 `MAX_SCREENING_CANDIDATES` 上限の中で扱う。

## Workflow契約

- Manual ONE-SHOT `full`: X有効。
- `article_validation`: X無効。
- `pending_retry_validation`: X無効。
- Scheduled Daily: **PAUSEDを維持**。Dormant contractにはX設定を保持するが、`if: false` のためApify/Gemini/Notionを消費しない。

## 受入条件

- X primary URL candidateが通常round-robin candidate poolへ入る。
- Raw X textはEvidence/Source Contextへ入らない。
- 既存URLとの重複がScreening前に落ちる。
- X取得は1 processにつき最大1回。
- X障害でも既存4ソースが継続する。
- Validation modeはApifyを呼ばない。
- Scheduled DailyはPAUSEDのまま。
- 決定論テストではGemini/Google/Notion/Apify実APIを0回にする。
