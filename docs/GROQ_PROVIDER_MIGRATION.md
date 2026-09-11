# Groq移行・開発仕様（Phase 1）

## 復元点
Gemini版 main / Run356: 966a0f1018fcf2d2c5da407d4f5f341e95c934a5
GitHubバックアップ: backup/gemini-run356-966a0f1
開発ブランチ: dev/groq-provider-foundation
このバックアップはGit管理下のコード・設定・履歴の復元点です。GitHub Secrets、外部Notionデータ、note下書き、VMの未コミット状態は含みません。これらは今回変更していません。
復元時はバックアップとの差分をレビューして通常のPRで戻す。mainの強制更新は不要。

## 実装状態
Provider共通要求・応答・例外とGroq GPT-OSS-120Bの検証用アダプタを追加。
production_pipeline.py の groq_saved_prompt_validation モードのみ接続。
通常Daily・Product Review子プロセスは既存Geminiのまま。完全移行・本番品質合格ではない。
自動fallback・SDK内部retryなし。エラー・空応答・出力打切り・不正usage・JSON/schema不一致は失敗扱い。
元のJSON Schemaを無断で緩和しない。schema指定時はjsonschema検証を必須とし、外部参照を禁止。
通信を伴わないprepareで入力サイズを事前点検。UTF-8バイト数と余白を用いる保守的推定であり実トークナイザ測定ではない。
超過時はプロンプトを切り捨てず停止。予算を満たすための品質指示削除はしない。

## 無料枠とローカル制御
公式公開値: 30 RPM / 1000 RPD / 8000 TPM / 200000 TPD。組織のConsole値が優先。
https://console.groq.com/docs/rate-limits
API仕様: https://console.groq.com/docs/api-reference
構造化出力: https://console.groq.com/docs/structured-outputs
一回の検証は一要求。SQLite台帳でローリング24時間3回/予約24000トークン、間隔65秒を上限として保守的に制限。
これは検証専用の独自上限であり、Groq公式のリセット時刻・残量を再現しない。
タイムアウト・HTTP失敗も予約を保持。台帳破損は失敗。上限制御を回避する台帳削除は禁止。
本番前に共通永続台帳、組織内別ワークロード、実レスポンスの制限ヘッダー、各工程予算を統合する必要あり。
共有永続台帳を使えない使い捨てCIからのlive検証は禁止。付属CIはofflineのみ。

## 検証方法
依存: Python 3.11+、requirements-groq-validation.txt（schemaを扱う場合）。
保存済みの正規Factoryプロンプトを以下のfixture形式で用意:
```json
{"stage":"calibration","prompt":"保存した完全なプロンプト","max_output_tokens":1000,"schema":{},"reasoning_effort":"low"}
```
schema不要時はschemaキーを省略。空schemaは実データの検証には不十分。
stageは screening / calibration / article / quality_gate / product_review。
AIIF_ONE_SHOT_MODE=groq_saved_prompt_validation
AIIF_GROQ_FIXTURE=<保存済みfixtureのパス>
AIIF_GROQ_REPORT=<結果JSONのパス>
python production_pipeline.py
既定は通信ゼロ。liveは追加で AIIF_GROQ_LIVE=true、GROQ_API_KEY、AIIF_GROQ_LEDGER（共有永続SQLiteファイル）必須。
キーは環境変数/Secretsに設定しコードやチャットへ貼らない。
レポートはfixtureハッシュ、工程、モデル、予約推定、実usage、生成本文を持つ。本文はコンソールには出さない。
quality_validated=falseは意図的: transport成功はFact/Editorial/Human等の合格を意味しない。
Notion保存・Ready変更・note投稿はこのモードには存在しない。

## 現行互換性の未解決点
pipeline.py _generate_via_chat がGemini専用の消費予約・監査を所有。
gemini_provider_resilience.py がモデルプール、retry、Product Reviewをラップ。
production_pipeline.py は通常ランタイムとProduct Review専用ランタイムを別々に組み立てる。
Product Reviewのmax_output_tokens=8000は入力を加える前に公開TPM値に達する。
Screening batch=25 / max output=5000、Calibration batch=50 / max output=4000も実プロンプトによる容量検証が必要。
次段階は正規保存プロンプトで容量測定、意味を保ったバッチ分割、工程予算・共通台帳・応答互換性の統合。
既存Gemini出力は比較資料であり正解ラベルではない。一次資料と現行品質契約を基準に独立評価する。

## 検証結果
13件のoffline unittest成功（予算超過、HTTP 429/503、timeout予約維持、不正出力、schema、永続上限、回復、Production入口からのGemini import隔離）。
GitHub SecretsのGROQ_API_KEY登録を確認。モデル一覧GETによる認証チェック成功（Run34655752401）、openai/gpt-oss-120bの掲載を確認。生成API呼出し0。実Calibration・記事品質・Daily E2Eは未実施。
最初のurllib既定クライアントでHTTP403、明示的なUser-Agent: AI-Intelligence-Factory/1.0で成功。同じ識別を生成transportにも設定。キー値・応答本文はログに出さない。
Groq Credential Checkは開発ブランチの当該workflowファイル変更時だけモデル一覧GETを行う。推論・SQLite検証予算・業務DBは使用しない。
