# Run129 Conversational Warmth Setup

目的は、Run128の専門性を落とさない日常翻訳に、note向けの親近感ある語り口を局所追加すること。

実装:
- `pipeline.py::_human_editorial_style_rules()` にConversational Warmth方針を追加。
- 「ですよね。」「やっぱり、」「なんですよ。」等は任意の表現例として許可し、必須化しない。
- Evidence / 数値 / 制約 / Security記述は冷静なトーンを維持。
- `pipeline.py::_reader_experience_signals()` にConversational Warmth / Marker Count / Overuseを0-API soft診断として追加。
- Article AuditへConversational WarmthとMarker Countを追加。
- Gemini call site、Notion schema、Hard Gateは変更しない。
