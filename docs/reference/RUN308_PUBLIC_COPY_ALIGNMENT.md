# Run308 — Public Copy Alignment

## Purpose

Run307で確定した商品価値を、公開LP・プロフィール・記事CTAを含むcurrent reader-facing copyへ一貫して適用する。

現行の中心メッセージは次を正本とする。

> **「このAI、使える！」を、根拠付きで判断できる。**

顧客提案は利用場面の一つとして残すが、商品・プロフィール・LPの主語にはしない。自分の開発、業務利用、必要に応じた提案へ横断的に使えるUse-Decision Intelligenceとして表現する。

## Current public source wording

公開面で情報源を列挙する場合は、現行Production authorityと一致させる。

- GitHub
- Hacker News
- ArXiv
- OfficialVendor（OpenAI / Anthropic / Google Gemini / 中国主要AIベンダー等の公式情報）

Product HuntはRun268以降active Sourceではないため、current public copyでは情報源として案内しない。歴史資料・互換コード内の記録は削除対象ではない。

## 手動反映用・固定note LP

公開中の固定noteは自動編集しない。以下を人間がnote編集画面で反映するためのcurrent handoffとする。

### 推奨タイトル

**「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB**

### ファーストビュー

**「このAI、使える！」を、根拠付きで判断できる。**

新しいAI、新しいモデル、新しい開発ツール。毎日のように情報は増えています。

でも、本当に知りたいのはニュースの数ではありません。

**「結局、これは使えるのか？」**

AI Intelligence Factoryは、自分の開発で使うときも、業務へ導入するときも、必要に応じて提案するときも、その判断を短時間で進めるためのDecision Intelligenceです。

### 情報源表記

**GitHub / Hacker News / ArXiv / OfficialVendor**

公式情報にはOpenAI、Anthropic、Google Gemini、中国主要AIベンダー等を含みます。

### 有料価値

月額1,980円で、重要な変化を絞ったDecision Brief、根拠を確認できる意思決定DB、試す・導入する前の判断メモを提供します。

無料noteは重要な内容を最後まで読める品質を維持します。有料価値は記事の続きではなく、**「で、使えるの？」を繰り返し判断する時間を短くすること**です。

### CTA

**月額1,980円の内容を見る**

## 手動反映用・現行プロフィール/署名

### 推奨短文

**AI・技術の「使える / まだ」を、一次情報とEvidenceから判断するAI Intelligence Factory。自分の開発、業務利用、必要に応じた提案に使えるDecision Briefと意思決定DBを運営しています。**

### 情報源を併記する場合

**GitHub / Hacker News / ArXiv / OfficialVendorの一次情報を継続的に確認し、「このAI、使える！」を根拠付きで判断できる形に整理しています。**

## 反映ルール

- `顧客` / `クライアント`を商品コピーの主語にしない。
- 顧客提案を禁止しない。自分の開発・業務利用・提案の一利用場面として扱う。
- 情報量・DB件数より「使えるか判断できる」を中心価値にする。
- current source listは **GitHub / Hacker News / ArXiv / OfficialVendor**。
- Product Huntをcurrent sourceとして表示しない。
- 記事CTAは **月額1,980円の内容を見る**。
- 根拠のないROI・時短率・売上効果を作らない。
- 無料noteの品質を意図的に落とさない。
- **公開noteはhuman-only**。この文書・Workflow・Guardから公開noteの本文変更や公開操作を自動実行しない。

## Verification scope

Run308 Guardはcurrent surfaceのみを検査する。Run268/270等の歴史資料まで文言置換して監査証跡を壊さない。

Guard対象:

- `docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md` の固定LP current section
- `run296_editorial_format_v2.py` のcurrent article CTA
- `PAID_PRODUCT_CONTRACT.md` のnote有料導線
- 本Run308 handoff

Run308はzero-network / zero-provider。Gemini API、Notion schema、Evidence、Decision Score、Source Scoreを変更しない。
