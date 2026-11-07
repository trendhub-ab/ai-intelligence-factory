# AIIF Next｜独立再構築 実施計画（2026-10-25）

**親正本:** `docs/superpowers/specs/2026-10-25-aiif-next-independent-system-canonical.md`
**既存main保全基準:** `4032060c6b9919ab2a05849e5607d666f503361f`
**現在の状態:** 方針承認済み。独立リポジトリは未作成。旧Production、V1/V2、Daily、note、Notionは変更しない。

## 実行原則

1. 最初から巨大なProductionを作り直さない。**創作品質の実証を先に行う。**
2. 新コードを旧Production内部へ増築しない。既存ツール群は参照してよいが、無条件移植しない。
3. 旧システムのゲートを省くことと、不要な管理制約をWriterのプロンプトから切り離すことは別。**事実確認、安全性、公開の権限を軽減しない。**
4. API利用上限、実行時刻、品質評価ルーブリック、保管先、秘匿性は、実行前に明文化する。プロバイダの障害は隠さない。
5. 収益に影響する指標は「採用できる1記事の総費用」と「実際の読者行動」で判定する。

## Step A — 新リポジトリ開設（要独立した実行権限）

- 非公開リポジトリを新設する。名前は仮 `ai-intelligence-factory-next`。既存RepoとActions secrets、権限、環境変数、Notion DB、配信トークンを共有しない。
- `main` を保護、branch/PRで開発、CIは最初すべてZERO-API。
- この正本、実施計画、過去のP5評価ルーブリックの**公開可能な要約**を移植する。未公開原稿・暗号鍵を移植しない。
- 新リポジトリを開設していない間は、新Writerの新規実装を既存mainへ登録しない。

## Step B — Phase0（Provider-free Research/Creative境界）

- `EvidencePacket`: 事実ID、一次ソースURL、根拠の範囲、条件/留保、仕組み、疑問・不明点。検証済みフラグは検証者が付与し、Writerは付与しない。
- `CreativeWriter`: EvidencePacket→日本語記事1本。管理スコア・決裁ラベル・Notion列・配信情報を入力しない。短く固定されたvoice policyを持つ。5段階JSONを必須としない。
- `IndependentFactReview`: 記事内主張↔Fact IDの照合、出典条件の欠落検出、重大誤りでNO-GO、事実に必要な局所修正のみ。
- `EditorialReview`: 実記事を匿名100点方式で複数回評価。モデルやプロンプトの識別情報は採点後に開示。
- Source/FactReviewの実証がない時点で、データを公開用Readyとしない。
- TDD: Evidence欠落、出典なりすまし、無根拠な主張、偽のApproval、未承認publish、未公開原稿漏えいを拒否するテストを先に書く。

## Step C — Phase1（明示承認後の小さな実API実験）

- 固定3テーマ（FFT、Elastic、Claude）を用いる。同一モデル・同一Fact pack・同一API transport/設定で旧P5と新Writerを公平に比較し、事前登録された採点指標を変えない。
- 各方式各題材で複数回生成が望ましい。少数しか成功しなければ不確実性を明示し、その結果を本番昇格に使わない。
- Gemini APIは**実行ごとに明示GOが必要**。予算超過・503/504はfailureとして数える。実験結果は非公開/暗号化。
- まず新Writerの有効性を判定し、Evidence/Fact/Publication検証の成功を別に測る。
- 目標90点級は**安定性と原稿品質**に対して設定。数字合わせ・文章の長さだけで判断しない。

## Step D — Phase2（運用の最小化）

- 原稿が優位と確認できてから、Research収集→Fact Review→編集承認→note非公開下書き→有料Decision DBの順で1機能ずつ追加。
- 旧V1/V2/ProductionとNextの配送ID、二重作成、権限、停止・再開契約を独立監査する。
- 一回で全面切替せず、shadow → limited → generalという段階リリースを要する。

## Step E — 事業上の採用/撤退基準

- レビュー合格原稿率、重大事実誤り率、事故ゼロ、原稿の質のばらつき、総コスト、日々の安定性を同条件で比較。
- 無料記事で読者が続きを読み、有料導線に進むかは、リリース後に実測する。
- Nextが優位性を示せない場合は旧Productionを継続し、Nextを止める。
- 優位性を示した場合も、旧Productionの廃止は別途OWNER GOが必要。

## 緊急停止と原状回復

- 旧システムの保全: `trendhub-ab/ai-intelligence-factory` mainと既存運用を変更しない。API認証情報、DB権限、定期実行を勝手に移動しない。
- Nextで事故: Nextへの権限・外部公開を止め、新システム側の処理を隔離。旧Productionのデータ・配送に手を触れず復旧。
- 置換後に問題発生: 切替機能を再設定して旧系に戻し、重複記事・会員権限・未送達イベントを照合。**restore point SHAへの破壊的resetは行わない**。

## PR管理

- 旧 `PR #876` は「既存repo内でのWriter独立試作」の記録として閉じ、未マージで保存する。
- 本文書を含むdocs-only PRを、旧リポジトリ側の意思決定・引き継ぎ資料として維持する。CI合格と**別途MERGE GO**なしでmainへ統合しない。
- 新リポジトリにおける実装/秘密情報/API実験/公開は、それぞれ別の審査と承認を必要とする。
