# AI Intelligence Factory Run292 仕様追補

## 目的

Run291の実private draft監査で、既存GenRec下書きに対して `Private draft visible body does not match the approved presentation` が発生した。

原因調査により、draft作成経路と監査経路で「可視本文の期待値」の生成方式が一致していないことを確認した。

- draft作成: `_markdown_to_safe_html()` でMarkdownを安全HTMLへ変換してnoteへ貼付
- Run291監査: `_plain_manuscript_text()` で簡易plain化して比較

`_plain_manuscript_text()` はdraft挿入時の軽量smoke check用であり、fenced code blockの内容を削除する。一方、noteへ貼付されたsafe HTMLではcode block本文は可視である。この差により、正しいdraftでも文字数・境界判定が誤る可能性がある。

## Run292の変更

### 1. Renderer-faithful expectation

`run292_note_rendered_body_audit.py` を追加する。

監査用期待可視テキストは、draft作成時と同一の `_markdown_to_safe_html()` の出力をstdlib HTMLParserで可視テキスト化して生成する。

これにより、以下を含む実表示を期待値へ反映する。

- fenced code block本文
- heading本文
- list item本文
- blockquote本文
- link label
- inline emphasis / codeの表示文字

Publication Contract本文そのもの、Run222 presentation transform、note editorへの書込み方式は変更しない。

### 2. Gateは緩和しない

既存Run291のfail-closed条件を維持する。

- expected prefixが実画面に存在
- expected suffixが実画面に存在
- visible length ratio 0.82〜1.30
- Sources / Evidence がCTAより前
- body先頭にtitle重複なし
- title一致
- body H1なし
- heading構造維持
- eyecatch存在
- editor geometry正常

変更するのは比較対象となる期待可視テキストの生成方法だけである。

### 3. Safe failure diagnostics

実監査が失敗した場合も未公開本文を外へ出さず、以下の非コンテンツ指標だけを結果ファイル・GitHub Step Summaryへ残せる。

- diagnostic_code
- expectation_mode
- actual / expected / legacy expectedの文字数
- renderer delta / ratio
- visible length ratio
- prefix / suffix match
- exact match boolean
- containment boolean
- common prefix / suffix ratio
- Sources存在 / CTA存在 / 順序
- duplicate title prefix boolean
- code fence marker count

禁止する出力:

- unpublished title本文
- manuscript本文
- actual body本文
- expected body本文
- private draft URL
- screenshot
- browser storage state

### 4. Workflow

`note-private-draft-audit.yml` の実ブラウザ監査だけRun292 entrypointへ変更する。

preflightは既存Run291のcurrent Ready / 投稿準備中 / public evidenceなし判定を維持する。

監査失敗時もsummary stepを `always()` で実行し、安全診断だけを残す。

VMは従来どおり、start-cloud-vm成功後は監査成否に関係なく `stop-cloud-vm` を必ず実行する。

## 不変条件

- Gemini/model calls: 0
- new draft creation: 0
- draft mutation: 0
- public note release: 0
- screenshot artifact: 0
- unpublished content artifact: 0
- Daily: PAUSED
- Publication policy / article generation logic: unchanged

## 反証

Run292専用テストでは少なくとも以下を検証する。

1. fenced code本文がrenderer-faithful期待値では保持される
2. 同じrenderer表示ならvisible ratio=1.0でPASS
3. 真の本文不一致はfail-closed
4. title重複はfail-closed
5. CTAがSourcesより先ならfail-closed
6. safe failure resultに本文・title・URLを含めない
7. Run292 moduleにmutation/publication/screenshot/network-write surfaceがない
8. workflowのsafe summaryは失敗時も実行される
9. VM stopは監査失敗時も維持される

Run292専用テストはRepository-wide Falsification Guardにも明示追加する。
