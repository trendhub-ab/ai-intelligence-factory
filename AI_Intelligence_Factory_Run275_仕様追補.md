# AI Intelligence Factory — Run275 仕様追補

更新日: 2026-09-07

Run275の目的は、Run274後の実ONE-SHOTで残った **Ready 0** を「Gate緩和」ではなく、Reader診断の誤検知修正と弱いfallbackモデルでも効く編集圧縮で改善することである。

## 1. Run31実Productionで確定したこと

対象: Daily Intelligence & Content Pipeline [ONE-SHOT] run #31 / run ID `34092602898`

- Collected: 198
- Screened: 52
- Stock: 7
- Deep Dive attempts: 3
- Generation Completed: 3/3
- Evidence Sufficient: 3
- Evidence Insufficient: 0
- Deep Dive Calls Avoided by Evidence Gate: 0
- Ready: 0
- Pending Retry: 0
- Fact Gate Failed: 1
- Human Appeal Review: 1
- Hard Blocked: 1
- Needs Editorial Review: 1

Run274のZero-API Evidence Backfillは、このrunではEvidence preflight脱落が0件だったため作動条件そのものが発生しなかった。したがって次の主要ボトルネックはEvidence探索ではなくReader Value / Human Appealである。

同時にRun272の時間制御は実効性を確認した。Production全体は約565秒、`product.delivery_maintenance` は約45秒まで短縮し、旧runで観測した約934秒の外部provider retry tailは再発しなかった。

## 2. Reader診断の反証結果

実Artifact 3稿を診断実装と照合した結果、本当に読みにくい稿と、診断の狭い語彙・構造認識による誤検知が混在していた。

### 2.1 Opening Reader Bridge

既存診断は本文後段では `でしょうか` をReader Questionとして認識する一方、opening bridgeでは認識していなかった。そのためVT Code稿の「不安を抱くのではないでしょうか。」のような明示的読者問いかけが、opening accessではREVIEWになる矛盾があった。

Run275では、同一診断内ですでにReader Proximityとして認めている問いかけと、`あなた` / `私たち` に具体的な困りごと・懸念・選択が結びつくopeningをStrong Reader Bridgeとして扱う。ただしopening technical density 42/1000以上は従来どおりREVIEWとし、高密度稿を問いかけ1文だけで通さない。

### 2.2 Visible Heading Rhythm

既存診断はMarkdown headingを本文から削除してから連続説明段落を数えていたため、読者には明確に節が切り替わっているのに「説明が3段落以上連続」と判定できる構造だった。

Run275ではvisible headingを説明runのbreakとして扱う。見出しがない3連続説明は従来どおりREVIEWであり、headingを置けば内容密度を無条件で許可するものではない。

### 2.3 Acronym Explanation / Entity Label

既存診断は略語の最初の出現付近だけを見ていたため、後段で `CLI（文字入力で操作するツール）` と正しく説明してもCLIがunexplainedのまま残り得た。また `VT Code` / `LM Studio` のような固有ラベルの一部も略語として数えられた。

Run275では次だけを訂正する。

- 同じ本文内の有効な括弧説明・平易な役割説明が確認できる略語はunexplainedから外す。
- 2文字大文字tokenが全出現で同一TitleCase語とだけ結合する場合に限り、stable compound entity labelとして扱う。
- `PC` は一般読者向け通常語としてunexplained jargonから除外する。
- `VRAM` / `MCP` 等の実技術語は、説明がなければ従来どおり残す。

## 3. Gateを緩めない契約

Run275の精度補正は既存Signal結果を全消去しない。

- 技術密度、長文cluster、jargon dense paragraph、implementation overload等の既存実質品質signalを維持する。
- Anthropic実稿のようにopening density約49.5、technical density約46、jargon dense paragraph 13の稿は引き続きREVIEWである。
- Information Budgetは、既知の全triggerが消えた場合だけGOODへ戻せる。
- Fact / Evidence / Publication / Decision Gateは変更しない。
- Reader-only failureを理由とする追加Gemini retryを禁止するRun273契約を維持する。
- provider/model/network call siteを追加しない。

## 4. 弱いfallbackモデル向け編集圧縮

Run31では3.6 / 3.7 / 3.8が503でrun-local unavailableとなり、多くの生成が3.5 fallbackへ流れた。Gateをモデル性能不足に合わせて下げるのではなく、Run226 / Run228の既存promptを短い実行順へ強化する。

- 冒頭: 読者の困りごと・迷い・選択 → 普通の言葉で意味 → 必要な場合だけ正式名称。
- 最初の段落を製品名・略語・実装名の紹介から始めない。
- 正式名称・略語・実装名・フラグ名はDiscovery / 重要制約 / Decisionに必要な時だけ出す。
- 同じ節で長い技術説明が2段落続いた場合、3段落目を足す前に意味・制約・判断へ進む。
- Evidence上重要な数値・条件・反証・制約は削らない。
- 親しみ語、比喩、問い、短文の回数ノルマは作らない。

## 5. 日本語surface精度

Bobbin実稿では `この誤検知がに減少しました。` という明白な助詞衝突が最終稿に残った。Run275は `がに` の後ろに減少/増加/向上/低下/改善/悪化/変化の活用が直結する狭いpatternだけを高確度surface defectとしてREVIEWに追加する。一般的な日本語文法推測へ拡張しない。

## 6. Runtime構造

新しいhistorical runtime layerは追加しない。`reader_quality_precision.py` はRun268/269と同様に `production_pipeline.py` のcurrent precision overlayとして、全historical quality layerのinstall後に適用する。

このoverlayは:

- zero API
- zero model call
- zero Notion write
- zero browser
- idempotent

であり、既存runtime wrapper orderを変更しない。

## 7. 反証テスト

最低限、以下を通す。

1. `でしょうか` を含む低密度Run31型openingはGOODへ訂正される。
2. 同じ問いかけでもopening technical density 42以上ならREVIEWを維持する。
3. visible headingで区切られた説明段落はuninterrupted runとして連結しない。
4. headingなし3連続説明はREVIEWを維持する。
5. 後段で正しく説明されたCLIはunexplainedから外れる。
6. `VT Code` / `LM Studio` はstable compound labelとして扱えるが、未説明VRAMは残る。
7. Bobbin実例 `誤検知がに減少` をblockする。
8. Anthropic型の真に高密度な稿はInformation Budget / Jargon / Accessibility REVIEWを維持する。
9. overlayにprovider/model/network call siteが存在しない。
10. Repository-wide Falsification / Integration Reconciliation / Notion Access Policy / Synthetic Productionをすべて通す。

## 8. 完成判定

技術的greenだけをRun275の事業成功としない。

次の実検証では、Free Tierを浪費するFULL連打を避け、まずcurrent quotaと強いFlashモデルの利用可能性を確認したうえで、可能なら対象を絞ったarticle validationを優先する。最終的な成功条件は **current-policy Readyが実際に1件以上生成され、Note Ready同期からprivate draft生成候補まで到達すること** である。
