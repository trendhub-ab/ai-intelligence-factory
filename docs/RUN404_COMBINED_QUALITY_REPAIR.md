# Run404 — Combined Quality Repair

## 目的

1回しか使わない既存Quality Retryで、`score_narrative_mismatch`とReader Valueの密度問題が同時に存在する場合に、両方を同じ修復で解消できる確率を上げる。

## 背景

RubyGems実記事では Decision Score=54 / WATCH に対して、タイトル・導入・本文・結論の一部が強い危機・即時対応トーンを維持し、`PUB_SCORE_NARRATIVE_MISMATCH`が残った。同時に `dense_report_cluster` / `multi_axis_reader_weakness` も残った。

旧ガイダンスはScore不整合を主に記事終盤で局所修正する指示だったため、タイトルや導入の強い緊急度表現が残りやすかった。

## 契約

- `score_narrative_mismatch`では MANAGEMENT DATA の Decision / Decision Score / Decision Reason / Action を正とする。
- タイトル → 導入 → 本文 → 結論の全Reader-visible surfaceで、緊急度・推奨強度を同じ行動距離へそろえる。
- WATCH / WAIT / AVOID では、Scoreに比べ過度な危機・断定・即時行動表現を弱める。
- Decision Score、Evidence、事実、数値、重要制約は変更しない。
- Reader密度問題が併存する場合、まずDecision整合を修正し、その後で重複説明・汎用前置き・不要な実装列挙を圧縮する。
- 新事実・新因果・架空経験・Evidence外の数値を追加しない。
- 既存のQuality Retry回数、Gemini request budget、Fact/Evidence/Publication Gate閾値は変更しない。
- 通常Daily、Pending Retry所有権、Notion/note契約、Xロジックは変更しない。

## 検証

`tests/test_run404_combined_quality_repair.py`で以下をゼロAPI検証する。

1. Score mismatch修復がタイトル・導入・本文・結論を対象にする。
2. ScoreとReader密度の併存時、Decision整合→圧縮の順序を固定する。
3. Evidence・事実・数値・重要制約を固定する。
4. 密度修復が新しい観点を追加して長文化しない。

## 公開契約

Run404は記事品質修復のみ。note公開権限は変更しない。今回の運用目標はprivate draft作成までで、公開は手動とする。
