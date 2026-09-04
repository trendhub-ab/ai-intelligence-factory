# Run229 — Eyecatch Title Editorial Compression

更新日: 2026-09-04

## 目的

公開noteアイキャッチの**タイトルだけ**を改善する。

今回の確定方針:

- 画像生成は導入しない。
- 背景、ネットワークイラスト、ブランド、カテゴリ、年月、既存subheadlineは現状維持。
- Gemini 3.5 Flashの既存1 requestを、タイトル短文化 + 改行 + 強調位置のディレクションへ拡張する。
- 追加Gemini requestは0。
- 画像生成APIは0。
- 失敗時は現行deterministic eyecatch rendererへFail-Safeする。

## タイトル契約

### 入力

記事の公開タイトルをclean public copyとして最大96文字までGemini 3.5 Flashへ渡す。
従来の48文字pre-truncationをタイトルディレクション前には適用しない。

### eyecatch_title

- 記事タイトルと同一である必要はない。
- 元タイトルの事実・主題を圧縮するだけで、新しい事実・数値・性能・因果・評価を発明しない。
- 製品名、モデル名、バージョン番号など記事識別に必要な固有情報を維持する。
- 理想15〜45文字。
- Hard Max 52文字。
- 元タイトルが短く強ければ、そのまま使用可。
- SEOブログ的な「徹底解説」「完全ガイド」「まとめ」「最新情報」等を新規追加しない。
- 元タイトル以上に断定を強めない。

### title_lines

- `eyecatch_title`を改行で分割するだけ。
- 1〜3行。原則2〜3行。
- 行頭禁則・行末禁則を維持。
- 固有名詞・英単語・複合語の途中で切らない。

### font

- Noto Sans JP Black系の既存方針を維持。
- Gemini requested range: 52〜76px。
- Run181の既存zero-API geometry boostにより最大80pxまで安全に拡大可能。
- 760px geometryを超える場合はvalidationでFail-Closed。
- 52px未満へ縮小して押し込むことはしない。

### highlight

- `highlight_text`は`eyecatch_title`内の完全一致substringのみ。
- 結論・問い・含意を原則優先。
- 短い単語だけ、製品名だけ、タイトル全体は避ける。
- Run182/183の既存Orange + scale rendererをそのまま利用する。

## セマンティック安全弁

完全な意味判定をdeterministic codeで偽装しない。
代わりに以下をHard Guardとする。

- 最大52文字。
- URL / Markdown制御文字を拒否。
- source titleに含まれる明白なLatin product/model/version identifierをeyecatch titleが落とした場合はreject。
- `title_lines`を連結した文字列が`eyecatch_title`と一致しない場合はreject。
- subheadlineは既存文字列のpartition以外を許可しない。
- kinsoku / width / font geometry validation失敗はreject。

Reject時は再試行せず、既存deterministic rendererへfallbackする。

## API / Quota契約

- Model: `gemini-3.5-flash`
- `request_kind="eyecatch_layout"`
- `thinking_level="minimal"`
- 1 eyecatchにつき最大1 layout request。
- Retryなし。
- Fallback modelなし。
- Deep Dive budgetとして数えない既存契約を維持。
- 画像生成request: 0。

## 変更しないもの

以下はRun229の対象外。

- `editorial_eyecatch.py`の背景・ネットワークイラスト
- 右側visual motif
- assets / image generation
- category/date UI
- brand logo
- subheadline生成ロジック
- Run181 visual balance geometry
- Run182 orange emphasis renderer
- Run183 emphasis scale
- note本文
- Evidence / Decision / Publication Gate

## Production不変条件

> タイトルは改善するが、アイキャッチの画像デザインは現状維持する。

> 既存1回のGemini 3.5 layout requestの範囲内で完結し、画像生成API・追加model callを導入しない。
