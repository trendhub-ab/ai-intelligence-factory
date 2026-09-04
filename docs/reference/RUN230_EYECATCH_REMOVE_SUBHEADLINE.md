# Run230 — Eyecatch Lower Lead Removal

更新日: 2026-09-04

## 目的

公開noteアイキャッチの下部に表示していた説明文（subheadline / lead）と、その左側の青いアクセント罫線を完全に削除する。

## 確定仕様

- 下部説明文を表示しない。
- 下部説明文用の青い縦罫線も表示しない。
- 背景、右側の既存ネットワークビジュアル、ブランドロゴ、カテゴリ、年月は変更しない。
- Run229のタイトル短文化・改行・文字サイズ・オレンジ強調ロジックは維持する。
- タイトルの既存Y位置・左右geometryは原則維持し、下部削除を理由にビジュアル構造を再設計しない。
- 画像生成APIは導入しない。

## Gemini 3.5 layout request

Run230以降、既存の1回の`gemini-3.5-flash` eyecatch layout requestはタイトル専用とする。

返却schema:

- `eyecatch_title`
- `title_lines`
- `title_font_size`
- `title_line_gap`
- `highlight_text`

以下はschemaから削除する。

- `subheadline_lines`
- `subheadline_font_size`

下部説明文を生成するための追加requestは行わない。

## Renderer

### Run181 / Run182 / Run183 path

- 既存背景を描画。
- ブランドを描画。
- category/dateを描画。
- Run229タイトルを描画。
- Run182/183のorange emphasisを維持。
- その後すぐPNG保存し、下部説明文・縦罫線を描画しない。

### deterministic fallback

Provider / JSON / semantic validation / geometry失敗時も、Run180内のtitle-only deterministic fallbackを使用する。

Fallbackでも:

- 既存背景を維持。
- 既存ブランド・category/dateを維持。
- 従来のdeterministic headlineを描画。
- 下部説明文を描画しない。
- 追加model callを行わない。

## API / Cost契約

- Gemini eyecatch layout request: 最大1回 / eyecatch（既存契約維持）
- Image generation request: 0
- Retry: 0
- Fallback model: 0
- 下部説明文削除による追加コスト: 0円

## 変更しない領域

- note記事本文
- Evidence / Fact / Decision
- Publication Gate
- Notion DB
- Member product
- eyecatch背景ビジュアル
- topic-specific画像生成
- Run229のタイトル編集方針

## Production contract

> アイキャッチは「ブランド + タイトル + 既存背景ビジュアル + category/date」で構成し、下部説明文は表示しない。

> 画像生成は行わず、現行ビジュアルを維持する。
