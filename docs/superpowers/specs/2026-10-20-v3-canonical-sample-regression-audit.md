# V3 P2 文章品質回帰監査 — 2026-10-20 (read-only evidence, no API)

## 判定
**QUALITY NO-GO / 技術検証 PASS。** 過去に採用したサンプル全文との厳密な同等性判定は **UNVERIFIED**。正本全文を取得・固定するまで「正本再現済み」と表明してはならない。

## 再現証拠
- GitHub Actions Run: https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39343016945
- Artifact: `editorial-engine-v3-phase0-checkpoint`, ID `12229703339`。 `raw_results.json` に各ケースの5段階出力と最終稿がある。
- Run は `C_ONLY_REFINEMENT`、3/3 完了、provider_calls=3、検証PASS、A/B byte identical。これらは**文章品質の合格を意味しない**。
- 実装: `experiments/editorial_engine_v3_phase0/prompts.py` (P2 branch)。以下は実コードと成果物の照合結果。

## 確認した原因（推測と区別）
1. **プロンプトの契約衝突（確認済）**: `C_EDITORIAL_PERSONA` は「Writer自身の一人称『私』」を要求し、`Persona Article Generation` は「一人称『私』で自然な反応」、bundle は「一人称『私』を…必ず残す」と要求する。一方、P1/P2は「『私は驚いた』を増やすだけの演出は禁止」「一人称を毎記事の冒頭に強制しない」。必須の一人称と自然さが緊張し、機械的な内省文を誘発しうる。
2. **実際の出力への反映（確認済）**: FFT最終稿は「私は」系が5箇所、「私にはそこが不思議でした」など内省が連続。Elastic Transformer最終稿は「私は…思い込んでいました」「驚きました」を先行させる。Claude最終稿は「私」が1回で、同じ制約下でも差がある。したがって原因を一人称の必須化だけに断定はできない。
3. **後段での平坦化を主因とは断定できない（確認済）**: FFTの初稿1189文字→Fact-Safe Review1053文字、Transformer1126→1082、Claude896→896。問題の内省表現は初稿から存在する。少なくとも「Fact-Safe Reviewだけが魅力を消した」という仮説は支持されない。
4. **入力と出力の専門語の距離（確認済）**: Transformerは導入でS/B/L、推論、Transformer等を先に置き、素朴な問いより説明が先行。FFTもO(n log n)を導入冒頭に置く。P2の「専門用語は必要な場合だけ使い、初出では日常語で短く説明」という意図を、実際の読み始めやすさの合格条件として検証できていない。
5. **評価ゲートの欠落（確認済）**: `proof verify` はcase set、fingerprint、記事レイアウト、Fact-Safe整合、A/B同一性などを検証するが、採用サンプルとの読者体験の同等性を検証しない。PASSと魅力の乖離は設計上説明できる。

## 未確定
- **正式採用サンプルの全文・固定ハッシュ・保存先が未確認**。サンプルの要旨や会話中の一節を全文正本の代用にしない。
- モデル自体の限界、5段階構成そのものの優劣、Fact-Safe Reviewの意味的損失率は、この3例だけでは断定できない。
- 採用サンプルとの再現性や実読者の評価は未測定。

## 次の実装の前提条件
1. 過去の採用サンプル**全文**をrepo内のimmutable referenceとして登録（出典・承認日時・SHA256）。取得できなければSTOP。
2. 正本から読者体験の評価基準を明文化する。表層の語尾・若者言葉・感情句の模倣ではなく、素朴な疑問、理解への段差、驚きの核心、自然な展開、中性的な言葉遣い、Fact忠実性を評価。
3. 既存Artifactの3ケースで**API追加0**のstage別比較を実施。初稿とレビュー後の両方を検証する。
4. 最小の変更のみRED→GREEN。原則は一人称の強制解除と、読者の問い・発見優先への置換。ただし正本照合前に本番プロンプトは変更しない。
5. Evidence/Fact/Publication Gate、A/Bベースライン、note配送、Dailyには触れない。API再試験はオフライン差分が十分改善した場合だけ、明示的なコスト上限を設ける。
6. 「CI GREEN」だけで公開・merge GOを宣言しない。**文章品質は別途Human Acceptance必須**。

## 意思決定
P2 PR #823 は保留。監査ブランチは設計証拠のみ。コード修正、Gemini呼び出し、main mergeは行わない。
