# Run132 Warm Rewrite + Length Budget

## 目的
Run131 fixed実稿で確認された「Reader Proximityが記事ごとに弱い」「親しみを足すほど長文化しうる」という2つの反証を同時に解く。

## 実装方針
- Reader Proximityを無料note記事の生成上の完成条件として明示する。
- 固定語尾を強制せず、既存の硬い説明文を1〜2箇所だけ自然な語り口へ**置換**する。
- 親しみ表現は追記しない。独立した雑談段落も作らない。
- 専門概念は2〜4個を中心にし、Decisionに不要な略語・内部実装・二重説明を圧縮する。
- 2,000〜3,200字の目安を超えそうな場合も、Evidence / 数値 / 制約 / 比較 / 反証 / Decisionを先に削らない。
- 3,400字超は0-API Article Audit上のInformation Budget REVIEWとするが、Hard Gateにはしない。
- Article Auditへ Article Character Count と Reader Proximity / 1000 chars を追加する。
- Gemini API call site、Notion schema、Product Review/会員DB保存経路は変更しない。

## 反証
1. 「ですよね」を必須回数化すると全記事が同じ口癖になる → 固定語は義務化しない。
2. 親しみを追加文で実現すると長文化する → 既存文の置換のみ。
3. 文字数をHard Gate化するとEvidenceの多い記事を誤Rejectする → Soft Reviewのみ。
4. 無料記事の圧縮が有料DBを薄くする → Product Review / Notion schema /保存経路は変更しない。
5. 親しみ不足でQuality RetryするとAPIとReject率が上がる → 再生成条件にはしない。
