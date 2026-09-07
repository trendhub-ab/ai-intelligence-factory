# AI Intelligence Factory — Run276 仕様追補

更新日: 2026-09-07

Run276の目的は、Run275後の実 `article_validation` で残った **Ready 0** を、Gate緩和や追加Gemini消費ではなく、Reader診断の「判定対象の単位」を正すことで改善することである。

## 1. 実Productionで確定したこと

対象: Daily Intelligence & Content Pipeline [ONE-SHOT] run #32 / run ID `34107417925`

- mode: `article_validation`
- Collected: 198
- Screened: 50
- Stock: 17
- Deep Dive attempts: 5
- Generation Completed: 3
- Evidence Sufficient: 2
- Evidence Insufficient: 1
- Fact Gate Failed: 2
- Publication Readiness Failed: 0
- Needs Editorial Review: 1
- Pending Retry: 1
- Ready: 0
- Candidate Publish Yield: 0/5
- Generated Publish Yield: 0/3

Geminiは15 attempts中9 success / 6 error。3.7 / 3.8は503、3.6も一部503となり、3.5 fallbackが複数稿を生成した。Run276はこのprovider状態に合わせてGateを下げず、追加model callも導入しない。

## 2. Run32で見つかった2つの診断不整合

### 2.1 30秒要約を長文記事として再診断していた

Run249は、タイトル・30秒要約・記事本文を結合したfinal projectionを作り、そこへ長文記事用 `_reader_experience_signals` を再適用していた。

Run249自体は必要である。実Run32でも、初回稿で以下の真正なfinal-surface欠陥を検出した。

- `final_surface_summary_fragment:なぜ重要？`
- `final_surface_summary_fragment:結論は？`

したがって「Run249を削除する」「final-surface Gateを一括で弱める」は不採用とする。

一方、30秒要約は意図的に約60〜110字へ圧縮された3つの短い回答である。長文記事診断では70字以上の段落について技術語密度を評価し、2段落がjargon-denseになるとJargon Translation / Non-Engineer Core Clarity等をREVIEWへできる。そのため、本文自体はGOODでも、短い要約を先頭に置いただけで記事全体のReader軸が悪化するカテゴリ不整合が生じた。

Run32のArXiv最終稿では本文Auditが以下だった。

- Plain-Language Bridge: GOOD
- Jargon Translation: GOOD
- Non-Engineer Core Clarity: GOOD
- Information Budget: GOOD
- Opening Non-Engineer Access: GOOD
- Reader Temperature Rhythm: GOOD

それにもかかわらずfinal-surface側だけが、

- `final_surface_multi_axis_reader_weakness`
- `final_surface_non_engineer_access_failure`

を返した。

Run276では判定対象を次のように分離する。

1. **長文記事Reader軸** — `parsed.note_draft` 本文を正本として評価する。
2. **タイトル** — Run249のquote balance等を維持する。
3. **30秒要約** — Fragmentと、複数行にまたがる高確度のjargon clusterだけを専用判定する。
4. **最終projection** — malformed Japanese等、組み立て後でしか見えない表層欠陥を引き続き検査する。

30秒要約は情報密度が高いこと自体を失敗にしない。ただし、2行以上が複数の未平易化略語・大量の異なる技術語で埋まる場合は `final_surface_summary_jargon_cluster` としてREVIEWする。

### 2.2 主題名詞の反復を「洞察の反復」と誤認していた

既存 `repetitive_insight` は、異なる3段落以上に共通する7文字片を数え、3片以上で反復と判定する。

Run32の最終ArXiv稿を実計算した結果、閾値を作った反復片は次だけだった。

- `エージェントの` — 4段落
- `エージェントが` — 3段落
- `すべてのデータ` — 3段落

これらは記事の主題・主語であり、同じ洞察・結論・判断を繰り返した証拠ではない。実装コメントは「technical nounの反復では判定しない」としていたが、コードは意味役割を区別していなかった。

Run276では既存7文字片detectorを捨てず、precision overlayで次を要求する。

- 3段落以上にまたがる反復片を従来どおり再計算する。
- そのうち、判断・行為・状態変化等のpredicateを含む反復片が2個以上ある場合だけsemantic repetitive insightと扱う。
- 主題名詞・助詞付き名詞句だけでは `repetitive_insight` を維持しない。

同じ判断文を3段落で繰り返す反証ケースでは、複数のpredicate-bearing 7文字片が残るため、真正な反復は引き続きREVIEWになる。

## 3. 実装契約

Run276は新しいruntime layerを追加しない。

### `reader_quality_precision.py`

- Run275 precision overlayを拡張する。
- canonical 7文字反復証拠を再現する。
- noun-only threshold accidentを除外する。
- genuine semantic repetitionは維持する。
- Fact / Evidence / Publication / Decisionに触れない。

### `run249_final_publication_surface_gate.py`

- title balanceを維持する。
- summary fragmentを維持する。
- malformed Japaneseのfull projection scanを維持する。
- article-wide Reader axesは本文に適用する。
- 30秒要約はsummary-specific high-confidence jargon clusterを評価する。
- disclaimer presentation repairを維持する。

## 4. 不採用とした修正

### Run249を削除する

不採用。Run32でsummary fragmentを実際に捕捉しており、final-surface防波堤として必要。

### Human Appeal閾値を下げる

不採用。本当に高密度・非平易・反復的な記事まで通すため、品質と顧客満足度を下げる。

### Reader-only retryを追加する

不採用。Run273の無料枠保護契約を維持する。Reader-only理由でGemini callを増やさない。

### 3.5 fallbackに合わせてEvidence/Fact Gateを弱める

不採用。provider品質と記事の事実品質は別問題であり、重大な事実誤認を許容しない。

## 5. Run276反証テスト

最低限、以下を固定する。

- Run32型のnoun-only repeated fragmentsは `repetitive_insight` を解除する。
- 同じ判断文を3段落で繰り返す場合は `repetitive_insight` を維持する。
- 30秒要約をprependしただけで長文Reader軸が悪化しても、本文がGOODならその誤差をfinal multi-axisへ変換しない。
- summary fragmentは引き続きWEAKにする。
- 複数summary rowが真正のjargon clusterならWEAKにする。
- 本文自体が4軸以上REVIEWならfinal-surfaceでもWEAKを維持する。
- Run276経路にprovider/model/network call siteを追加しない。
- Repository-wide Falsification / Integration Regression / Notion Guard / Live Acquisition Smokeをすべて通す。

## 6. 完成判定

Run276の**技術的完成**は全CI greenである。

しかし事業上の完成ではない。最終判定は別に行う。

1. mainへ安全にマージする。
2. 追加FULLではなく、低コストの `article_validation` を1回だけ実行する。
3. current-policy Readyが1件以上生成されることを確認する。
4. Note Ready fan-outからprivate draft candidate pathへ到達することを確認する。
5. 実際のprivate draft作成が検証できるまでnote E2E成功とは呼ばない。

Readyが再び0の場合は、Gateを下げず、新Artifactの最上位失敗原因だけを次の反証対象とする。
