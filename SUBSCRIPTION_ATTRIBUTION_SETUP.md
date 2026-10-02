# Free note → Subscription Attribution Setup

目的は、無料note記事を「販売商品」にせず、会員向け **意思決定DB + 月次サマリー** への獲得チャネルとして計測すること。

## 1. GitHub Repository Variableを1つ設定

Repository Settings → Secrets and variables → Actions → Variables で次を設定する。

- `SUBSCRIPTION_LANDING_URL`: 会員申込・説明ページの公開HTTPS URL

`daily.yml`はこのVariableを`pipeline.py`へ渡す。未設定・不正URLの場合も記事生成は止めないが、CTAとAttribution manifestは生成しない。

## 2. Ready記事に自動で入るもの

ReadyかつNotion永続化成功の記事には、原稿末尾の出典ブロック直前に次のCTAが入る。

- 無料記事は最後まで無料であることを明示
- 有料商品の価値を「意思決定DB + 月次サマリー」として訴求
- URLには`utm_source=note`、`utm_medium=free_article`、`utm_campaign`、`utm_content=<article_id>`、`aif_article_id=<article_id>`を付与

`article_id`はPrimary URLをcanonicalizeして作るため、utm差やDiscovery Source差では変わらない。

## 3. Attribution manifest

Ready確定後だけ、`subscription_attribution/articles/<article_id>.json`を生成しGitHub Contents APIで永続化する。

保存するのは記事単位のaggregate metadataだけ。メールアドレス、氏名、member/customer/payment ID等の購読者PIIは保存しない。

Telemetry保存失敗は記事品質と無関係なのでReadyを取り消さない。

## 4. 外部実績CSV

`subscription_metrics_template.csv`をコピーし、記事単位・期間単位のaggregate実績だけを入力する。

`attribution_method`は必須。

- `note_dashboard_only`: `note_views`だけ。加入・売上の帰属は主張しない。
- `tracked_cta`: `note_views`と`cta_clicks`まで。CTAクリックだけ追跡できる場合。
- `end_to_end`: 記事IDが申込/課金まで保持され、加入・継続・売上まで記事へ帰属できる場合。
- `manual_verified`: 人間が記事単位の帰属を検証済みの場合。

根拠レベルを超える数値を入れるとimportを拒否する。

## 5. 集計

```bash
python subscription_attribution.py \
  --metrics subscription_metrics.csv \
  --manifest-dir subscription_attribution/articles \
  --output subscription_attribution/metrics_rollup.json
```

主な出力:

- CTA click rate
- Subscriber conversion / click
- Subscriber conversion / note view
- Subscription revenue / 1,000 note views
- 計測coverage

## 6. 重要なFail-Closed

現段階では`metrics_rollup.json`をCommercial Value / Source ROI / Deep Dive Priorityへ自動反映しない。

実績件数が少ない、あるいは帰属精度が低い状態で記事選定を自己強化すると、偶然の1件を「勝ち筋」と誤学習するため。Revenue Feedback Loopは十分な実測データが溜まった後に別Gate付きで実装する。


## 7. Zero-model CV / コピー改善診断

`subscription_attribution.py` は集計と同時に
`subscription_attribution/conversion_copy_diagnostics.json` を生成する。

この診断はGemini/APIを一切使わず、集計実績だけから次を区別する。

- `CTA_COPY_OR_PLACEMENT`: 閲覧母数はあるがCTAクリック率が弱い。CTA見出し・価値提案・配置を人間レビューする。
- `OFFER_OR_LP`: CTAクリックは取れているが加入転換が弱い。membership LP・価格納得感・加入手順を人間レビューする。
- `TRACKING_GAP` / `POST_CLICK_UNMEASURED`: 計測不足。コピーを変更せず計測を先に直す。
- `INSUFFICIENT_DATA`: 母数不足。変更しない。
- `NO_COPY_CHANGE_INDICATED`: 現時点でコピー変更を示す材料なし。

記事・Source・Portfolio Topic・CTA Copy Versionごとに集計する。
今後のReady manifestには実際に表示したCTAの `cta_copy_id` / 見出し / リンクラベルを保存するため、
コピー変更後も旧版と新版を混ぜずに比較できる。

### 安全境界

- model calls: 0
- subscriber PII: 保存禁止
- public copy mutation: 0
- note publish/update: 0
- production ranking feedback: 無効のまま
- 改善案は「人間が見るべき箇所」の仮説だけ。置換コピーは自動生成しない

十分な実測が溜まった後だけ、人間承認でコピー実験を設計する。
