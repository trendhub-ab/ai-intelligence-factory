# V1 Daily Writerプロンプト組み立て順のゼロAPI監査（2026-11-05）

## 結論

2026-11-05のDailyは `human_narrative` を選択しているが、**送信された実プロンプトは、そのスタイルの単独定義だけではない**。Productionの`runtime_layers.py`はWriter計画、読者リズム、Yield、読者価値、A+、最終読者チェックを後段で合成する。

V1の実際の入力（完全Source Native Context、Evidence Metadata、Freshness、Quality Feedback、前回稿、記事ごとの表示バリエーション、Run内の記事順番）と、送信直前のプロンプトSHAを**2026-11-05時点で保存していた証拠がない**。現存するNotion公開用最終稿のみでは復元できない。**過去実プロンプトのSHAを捏造しない。**

## 追加した検査

- `offline_v1_writer_prompt_stack_receipt.py` は、実行時に必ず**2026-11-05 V1ソースのGit blobとLayer順序を照合**した上で、公開不可の合成（SYNTHETIC）入力だけで**既存のPrompt Builder・既知のPrompt変更レイヤー**を組み立て、各段階のSHA256とUTF-8バイト数を計算する。
- 実際の`content_generation_protocol.build_decision_prompt()`から始まり、`run226`、`run228`、`reader_value_review_bridge`、`run208`、`A+`、`run248`の**既知の指示合成順**を確認する。シミュレーションのレイヤー順は`runtime_layers.RUNTIME_LAYER_ORDER`と照合する。
- これはProductionの全モジュールを起動した完全なRun replayではない。Gates・実配送の証明ではなく、**コード上で確認されたWriter指示レイヤーの純粋な構成検査**である。
- 出力は`sha256`、段階名、長さ、ソース指紋、および未確認フラグのみ。プロンプト原文、Evidence、原稿、APIキー、ノートトークンは**出力しない**。
- **自動的なGEMINI / Notion / note呼出しは0回**。実際のDaily `production_pipeline.py`、`pipeline.py`、`runtime_layers.py`、各既存Writerの編集規則は変更していない。

## CI検査

```bash
python offline_v1_writer_prompt_stack_receipt.py
python -m pytest -q tests/test_offline_v1_writer_prompt_stack_receipt.py
```

プロンプト自体を公開CIログへ記録しない。所定のソースが少しでも変わると `V1_SOURCE_DRIFT`、指示のレイヤー順序が変わると `V1_PROMPT_LAYER_ORDER_DRIFT` として中断する。実際のモデル送信、外部通信、生成原稿保存は行わない。

## Nextの比較PRとの関係

- Next [Draft PR #121](https://github.com/trendhub-ab/ai-intelligence-factory-next/pull/121)：11月5日Ready 3本の本文品質監査。Human Appeal=`WEAK`なのにReadyになる例や、読者向け定型サマリーの固定挿入を確認。
- Next [Draft PR #122](https://github.com/trendhub-ab/ai-intelligence-factory-next/pull/122)：FFT、Elastic、Claudeの3候補のEvidence／固定v0.4側プロンプト指紋。未検証FactとV1プロンプトの不在を明示。
- **本V1 PR**：V1の追加レイヤーの存在を確認し、合成入力で再現できる範囲をハッシュ化。**#122の`v1_human_narrative_prompt_sha256=null`を埋めてよいという証拠にはならない。**

## 正規の同条件比較への残作業

1. V1実行入口のProduction全レイヤーを通した実プロンプトに対して、**実モデル送信直前**のSHAと全入力の照合情報を取得する安全な仕組みを、別途のOwner承認後に設計・レビューする。今日の本番コードやRunフローに今回のPRから介入しない。
2. Nextの3候補は構造上有効でも `CANDIDATE_NOT_HUMAN_VERIFIED` のまま。原典・数値・Qualifierの人手確認なしに新規モデル呼出しを行わない。
3. 同じEvidenceを両腕へ入力し、同モデル・同温度・同トークン上限で生成。公開面のReader SummaryとWriter本文は評価を分離する。
4. 匿名2名以上の実読採点で、好奇心・意外性の根拠・感情の自然な変化・中性的な口語調を確認。Gateや既存Reader Value閾値を先に緩めない。

## 絶対に実施していないこと

- Gemini呼出し、Writer r9〜r10.1の復帰、Next固定v0.4の変更
- 本番Daily開始、V1/Nextのmain変更、公開原稿の更新、note/Notion書込
- 過去Daily実プロンプトの完全復元・事実検証・ブラインド比較の採点

**Draft／No Merge。** オフラインCIがGREENでも、別途Ownerのマージ判断なしに取り込まない。
