# Run128 Non-Engineer Accessibility Bridge Setup

## 目的
「楽しくて分かりやすく、気づいたらAIやITに詳しくなっている」を、専門性・Evidence・Decisionを落とさず実現する。

## 実装
- `pipeline.py::_human_editorial_style_rules()` に非エンジニア向け翻訳ルールを追加。
- 難しい概念は「普通の言葉 → 必要なら日常例/比喩 → 正式名称・Evidence」の順で橋渡し。
- 高専門語密度では日常ブリッジを推奨。ただし恋愛・買い物・スマホ等の題材は固定しない。
- `_reader_experience_signals()` にPlain-Language Bridge / Jargon Translation / Non-Engineer Core Clarityを追加。
- Article Auditへ新3項目を出力。
- すべてsoft-only。Fact/Evidence/Decision/Human Appeal HARD Gateは変更しない。
- Gemini API追加なし、Notion Schema変更なし。

## 次のProduction確認
Real Article Regression 3本で、専門語が多い記事にも最低1箇所の自然な日常翻訳が入り、正式名称・制約・一次情報が残ることを人間監査する。
