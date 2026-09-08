# AI Intelligence Factory Run288 仕様追補

## 背景

Run287で、Hacker Newsのitem時刻を外部一次記事の「公開・更新」と誤表示していたpublication metadata provenance不具合を修正した。

Run287 merge前のCurrent-policy Ready Recovery #4ではNetflix TechBlog「GenRec」が以下を満たしてReadyへ到達している。

- Gemini 3.7 Flash deep dive HTTP 200
- Publication Readiness Gate PASS
- Human Appeal Gate ACCEPTABLE
- Notion Ready commit成功
- Note Ready current-policy source_ready=1
- pre-Run287 Publication policy SHA: `7417b204254b07547d319b145e3b6e9b2d0d5023f6e1b1d2fa7219b81b372e9d`

Run287は記事本文の意味を変更せず、公開ヘッダーの1行だけを次のように修正する。

- 旧: `公開・更新: 2026-08-15`
- 新: `Hacker News投稿日: 2026-08-15`

Run287 merge後はPublication Contract SHAが正当に変更されたため、GenRec旧Readyはstaleとなった。

その後Recovery #5を実行したが、3.7 / 3.8 / 3.6 / 3.5がすべてHTTP 503となり、別候補がPending Retryへ退避された。3.6の残りは1 requestである。

## 経営判断

GenRecはすでに全文生成・Fact/Publication/Human Appeal・Notion persistenceを通過している。Run287で変更すべき情報は、モデル生成ではなく決定論的metadata labelの1行だけである。

この状態で全文を再生成することは、

- 無料API枠を消費する
- 既に合格した本文を不必要に変える
- 新たなFact/Reader regressionを持ち込む

というコストとリスクがあり、顧客価値を増やさない。

したがってRun288は、旧Ready本文をモデルで再生成せず、Run287の1行だけを決定論的に変換し、新Publication Contractでcontent-addressed Ready blockを再発行する。

## Fail-closed条件

Run288は次のすべてが一致した場合だけ書き込む。

1. source pageのArticle Statusが現在もReady
2. sourceがHackerNews
3. primary URLがNetflix GenRecの固定slug
4. eyecatchが存在
5. 旧Ready blockのcontract IDが現行contract family
6. 旧policy SHAが `7417b204...372e9d` と完全一致
7. 旧caption manuscript SHAと旧body bytesが一致
8. current-policy Ready blockがまだ存在しない
9. 旧metadata lineが正確に1回存在
10. 新metadata lineが未存在
11. 変更行数が正確に1行
12. 新行を旧行へ戻すと旧body bytesと完全一致
13. append後にNotionから読み戻したbody bytesが新bodyと完全一致
14. 新captionがcurrent Publication Contractでvalid

1つでも満たさなければfail-closedで終了し、Readyを作らない。

## API / 公開境界

- Gemini/provider calls: 0
- fresh acquisition: 0
- screening: 0
- Product Review: 0
- eyecatch regeneration: 0
- private note draft: 0（Run288 workflow単体）
- VM/browser: 0
- public note release: 0
- Daily schedule変更: 0

Run288成功後、Note Ready syncでcurrent-policy source_readyを確認する。その後private draftは既存の明示的Note workflowで別途実行し、public releaseは引き続きhuman-onlyとする。
