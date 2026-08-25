# Run133 Reader-First Editorial Compression Validation — 2026-08-25

## Result
- Run133 dedicated tests: 5/5 PASS
- unittest discover: 691/691 PASS
- pytest: 691 passed + 19 subtests PASS
- Synthetic Full: 500/500 PASS
- Synthetic critical failures: 0
- Synthetic major failures: 0
- Production write isolation: true
- compileall: PASS
- GitHub workflow YAML: 8/8 PASS
- `_generate_via_chat(` call sites: 7 (unchanged)
- `genai.Client(` occurrences: 1 (unchanged)
- New Gemini API call: 0
- Notion schema change: 0
- Product Review / subscriber DB persistence logic change: 0

## Falsification / adversarial checks
1. **「会話表現を足せば親しみやすい」仮説を棄却**
   - 長文化とテンプレ口癖を招くため、既存の硬い文を置換する方式を維持。
2. **「全専門語を日常例で説明すれば分かる」仮説を棄却**
   - ARTICLEで覚える核心概念を原則2〜3個へ編集選択。4個目はDecision誤解防止に不可欠な場合のみ。
3. **「専門性＝技術名の多さ」仮説を棄却**
   - Evidence/数値/制約/比較/反証/Decisionは保持し、Decisionに不要な規格番号・略語・内部実装は圧縮。
4. **「文字数をHard Gateにすればよい」仮説を棄却**
   - 3,200字はSoft Ceiling。重要Evidenceのための超過は許容し、追加Gemini Retry / Reject条件には接続しない。
5. **「無料ARTICLEを薄くすると有料DBも薄くなる」経路を遮断**
   - Product Review / Notion subscriber persistenceは変更なし。ARTICLE専用編集ルールとして明示。

## Previous Run132 real-article counterfactual audit (0 API)
Run132 fixed実稿をRun133の新しい0-API診断へ再投入したところ、ユーザーの実読評価と一致して問題を検出した。
- ESP32: 5605 chars / Information Budget REVIEW / Implementation Detail Load REVIEW (16 identifiers) / Reader Temperature Rhythm REVIEW / jargon-dense paragraphs 20
- Kobo: 4393 chars / Opening Non-Engineer Access REVIEW / Information Budget REVIEW / Implementation Detail Load REVIEW (8 identifiers) / Reader Temperature Rhythm REVIEW / jargon-dense paragraphs 17
- MCP: 3996 chars / Opening Non-Engineer Access REVIEW / Information Budget REVIEW / Implementation Detail Load REVIEW (11 identifiers) / Reader Temperature Rhythm REVIEW / jargon-dense paragraphs 14

これにより、旧診断がReader ProximityをGOODとしながら記事全体の「難しい・硬い・長い」を見逃していた穴を補足できることを確認した。

## Local synthetic note
Synthetic Fullは既存のprovider-free SDK stubを用いて実行し、Gemini API callは発生していない。
