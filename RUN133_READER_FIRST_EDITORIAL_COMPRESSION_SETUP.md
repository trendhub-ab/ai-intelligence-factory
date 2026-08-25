# Run133 Reader-First Editorial Compression

## 目的
Run132 fixed実稿で、非エンジニア読者が「難しい・親しみがない・面白くない」と感じる問題を、人間の距離感と情報の引き算を同時に使って改善する。

## 反証から採用した設計
- 会話表現を追加すると長文化するため、親しみは既存の硬い説明の置換で作る。
- 全専門語を日常例で説明すると記事が膨らみ、Evidence/Decisionを圧迫するため、ARTICLEで覚える核心概念は原則2〜3個、不可欠な場合のみ4個まで。
- 一次情報にある技術名を全部本文へ転記しない。重要Evidence・数値・制約・比較・反証・Decisionは維持する。
- 硬い技術説明が2段落続いたら、次の段落は新しい雑談を足さず、既存文を読者の経験・具体場面・平易な一言へ書き換える。
- 本文目標を2,200〜3,000字、3,200字をSoft Ceilingにする。Hard Gateや追加Gemini Retryにはしない。
- 無料ARTICLEの圧縮をProduct Review / 有料Notion DBへ伝播させない。

## 0-API Article Audit追加
- Opening Non-Engineer Access
- Opening Technical Terms / 1000 chars
- Implementation Detail Load
- Implementation Identifier Count
- Reader Temperature Rhythm

すべてsoft-only。Fact / Evidence / Decision / Publication Hard Gate、Gemini call site、Notion schemaは変更しない。
