# AI Intelligence Factory Run405 仕様追補

## 目的
Run404適用後の実記事「OpenAI agents carried out an undisclosed attack on RubyGems」で、Publication ReadinessはPASSした一方、Reader Valueで `dense_report_cluster` / `multi_axis_reader_weakness` / `non_engineer_access_failure` が残った。Run405はGateを緩めず、既存1回のQuality Retryをより実行可能な指示へ具体化する。

## 実記事で確認した問題
最新Editorial Review原稿では、RCE、設定ファイル、攻撃用コメント、4段階の攻撃挙動、APIキー取得試行などの技術情報が連続し、その後に同じ危険性を再説明していた。Fact/Evidenceの欠陥ではなく、判断に必要な情報よりReader-visibleな技術列挙が多いことが主因だった。

## Run405契約
- API予算を増やさない。
- Gate閾値を下げない。
- Evidence、Fact、Decision、Decision Score、数値、重要制約を変更しない。
- Reader-density系の失敗がある場合、Decisionを変える中核メカニズムは本文前半で1つに絞る。
- 具体的挙動・列挙は原則3点以内に圧縮する。
- 正式名称・コメント文字列・内部部品名・実装手順が4個以上連続し、違いがDecisionを変えない場合は削除または意味カテゴリへ統合する。
- 1段落に新規専門概念を2個以上持ち込まない。
- 残した技術段落の直後に、同じEvidence範囲で「読者の判断では何が変わるか」を普通の日本語1文で接続する。
- 後段で同じ危険性・重要性を再説明せず、重要制約と次Actionへ進む。
- Score/Decision不整合が同時にある場合、先にScore/Decisionに合わせてタイトル→導入→本文→結論の緊急度をそろえ、その後に密度を圧縮する。

## 非変更領域
- Geminiモデルルーティング、503フォールバック、Persistent Budget
- 通常Daily / article_validationの予算
- Notion保存閾値
- Publication / Fact / Evidence / Reader Gate
- note公開契約
- Xロジック

## 合格条件
Reader-density理由があるQuality Retry promptに、上記の具体的圧縮契約が入ることをゼロAPIテストで固定する。実記事は再実行後に全Gateを再判定し、Acceptedの場合のみNotion Ready / note下書きへ進める。
