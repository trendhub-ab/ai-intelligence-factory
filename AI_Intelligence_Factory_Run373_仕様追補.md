# AI Intelligence Factory Run373 仕様追補

## Production起点

ONE-SHOT Run #60（workflow run `34974038312`）で、Run371/372反映後のarXiv metadata取得が429ではなく連続ReadTimeoutになった。

runtime-stateでは最初のrequest slot、bounded retryの2回目、最終ReadTimeout保存まで確認できた一方、`circuit_run_id`は前Run #59の値のままで、Run #60のcircuitは開かなかった。

したがってRun371の契約には次の非対称性が残っていた。

- 429 / 503: 1回でsame-run circuit OPEN。
- transport timeout: 最大1回retry後に終了するがcircuitを開かない。
- 500 / 502 / 504: 最大1回retry後に終了するがcircuitを開かない。

この状態では、後段Evidence Healthや別processのProduct Reviewが同一Run中に同じarXiv metadata APIへ再度アクセスし、同じtimeout pairを繰り返せる。

## Run373契約

Run371のbounded retry自体は変更しない。

その結果が`None`で、かつcurrent-run circuitがまだ開いていない場合だけ、次を適用する。

- transport exceptionが2回で尽きた場合: circuit status `0`（HTTP statusを捏造しない）でcurrent-run circuit OPEN。`last_error_type`は保持する。
- 500 / 502 / 504がbounded retry後も残った場合: 最終HTTP statusでcurrent-run circuit OPEN。
- 404等の恒久的client response: circuitを開かない。
- 429 / 503: Run371の既存即時circuitをそのまま維持し、Run373で再分類しない。
- fresh cache hit: 既存どおりcircuitより優先して利用可能。

## 安全境界

- 追加network requestは0。
- retry回数を増やさない。
- Source / Evidence / Fact / Publication / Reader Gateを変更しない。
- arXiv候補の存在判定やtitle integrity基準を変更しない。
- Notion、note、Gemini model routingを変更しない。
- Scheduled DailyはPAUSEDのまま。

## 事業上の意味

arXiv側が遅い日に、Mainで最大2回待った後、Evidence Health / Product Reviewで同じ待ちを繰り返す時間損失を止める。正常なSourceと記事生成へ実行時間を残し、`Ready >= 1 -> note private draft >= 1`の達成確率を上げるための運用安定化である。
