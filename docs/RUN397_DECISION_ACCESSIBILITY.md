# Run397 — Decision Accessibility Reader Gate

## Decision

AIIF Reader Gateの正式目標を「非専門家でも全文を平易に理解できる」から、**「非専門家でも核心と意思決定を理解できる」**へ変更する。

専門用語の存在や密度だけではFAILにしない。AI/OSS/開発ツール/認証/セキュリティ/arXiv/数理の題材では、正確性と判断に必要な専門語を保持する。

## 合格条件

専門性の高い題材で密度由来のReader診断を緩和できるのは、次をすべて満たす場合だけ。

1. 何の話か／何が変わったかが冒頭で分かる。
2. なぜ重要か、読者の判断にどう効くかが分かる。
3. できること、または重要な制約・限界が分かる。
4. 試す／比較する／待つ／見送る等の次Actionが分かる。
5. 判断に必要な専門語は初出時に短い役割説明があり、未説明の必須用語が残っていない。

## 題材別Plainness

- 一般AIサービス: HIGH
- 開発ツール / OSS / SDK / CLI / API / ライブラリ / インフラ: MEDIUM
- 認証 / セキュリティ / 暗号 / arXiv / 数理 / モデル構造: LOW

PlainnessがLOWでもFact/Evidence/Publication、日本語破損、重要制約、用語の橋渡し、Decision/Actionは緩和しない。

## HARD / REVIEW / PASS

- Fact / Evidence不備: HARD BLOCK（変更なし）
- 意味不明・文章破損: HARD BLOCK（変更なし）
- 未説明の判断必須専門語: REVIEW / Repair
- 専門語が多いだけ: 単独ではFAILにしない
- 専門語が多く、核心への橋がない: REVIEW / Repair
- 専門語が多いがDecision Accessibilityが成立: PASS可能

## Writer / Repair

WriterとReader Repairの双方へDecision Accessibility Contractを最終優先指示として追加する。

専門語を消すための長い比喩、会話句、身近な例の強制は禁止する。本文では必要な専門性を残し、初出時の短い役割説明で橋を架ける。Evidence、仕様、数値、正式名称は専門的なままでよい。

## Safety

この変更はReader精度のみを変更する。Fact/Evidence/Publication Gate、モデルの利用上限、Notion/note公開処理、Xロジックは変更しない。

`reader_quality_precision.py` はPublication Contractのpolicy fingerprint対象なので、この変更をmainへ昇格するとpolicy SHAは変わる。既存Readyの扱いはPublication Contractに従い、古いfingerprintを自動的に現行Readyとみなさない。
