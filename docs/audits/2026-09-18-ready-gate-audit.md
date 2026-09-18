# 実記事Gate / Ready生成経路の決定論監査（2026-09-18）

## GitHubから再取得した基準

- main: `e8d83ff854f9346fc5a414a1bcd24ecaa25226d4`（PR #396統合済み）。引継書のPR #386時点を基準にはしていない。
- 監査開始時のopen PR: 0。branch一覧と直近Actionsをread-only確認。
- PR #396 head `c69a8c77433b1cd3ad4863e328913859a03843c9`: Integration Reconciliation / Repository-wide Falsification / Notion Access Policy Guard SUCCESS。
- mainのSynthetic Regression / Repository-wide Falsification SUCCESS。
- GitHub上には既存ONE-SHOT #72の履歴も存在したが、本監査はそれをdispatch・再実行していない。
- 開始時Publication policy: `5eedd6393fe31817630979910fe27faf6afb5e3342e29e6c160c559a9dfb53b3`。

## 再現した不具合: 要約整形が自分のReader Gate違反を作る

`note_manuscript._compact_reader_summary()` は完結した先頭文が110文字を超えると、先頭110文字内の読点で切って返していた。`run249_final_publication_surface_gate._summary_fragment_issues()` は読点終わりの要約を `reader_value_review:final_surface_summary_fragment` として停止する。

このため、Writer / Quality Retry / Reader Repairが文を完結させても、共通の最終要約整形が再び文を壊し、Readyを妨げる構造が残っていた。Ready Rescueも同じ最終Gateを通るため、追加送信のできない1-request枠でこの整形不具合を受ける。

再現入力（118文字、完結文）:

> この仕組みは、確認済みの資料から判断に必要な情報を取り出し、担当者が参照先と注意点を見比べながら導入の適否を検討できるようにするものですが、利用環境によって結果が変わるため公開された事例だけを根拠に全社での採用を決めることはできません。

修正前は「ものですが、」までの70文字になり、後半の適用条件と否定結論が欠落した。これはReader判定の誤検出ではなく、整形が実際に作った欠陥である。

最小修正は、完結した先頭文をそのまま選び、文字数目安のために文中切断しないこと。新しい事実・句点・省略記号を作らない。未完結の入力に対する既存fallbackと、Run249の断片・専門語・日本語異常検知は維持する。110文字は完結文の条件・結論を切り落とす上限としては扱わない。

TDD:

- 修正前: 新規9ケース中 **8 FAIL / 1 PASS**。読点・カンマ・セミコロンによる条件切断、最終headerへの再適用を再現。
- 修正後: 新規ケースとRun103/104/249/276関連 **37 PASS**。独立レビュー後、実summary/projection builderからNotion payload・body hashまでの回帰を1件追加して **38ケース** に拡張。
- 元から未完結なWriter出力は引き続きGateで拒否する。

## 横断確認した境界

| 境界 | 確認内容 |
| --- | --- |
| 初回Writer / Quality Retry | `pipeline.generate_intelligence_report` の共通ループで整形→Fact→Editorial→Publication→Human Appeal/Readerを再実行。SOFTのみではretryしない。 |
| Reader Repair | Run208/360の通常retryとReader修復の所有権、PR #392/#393のPending修正を基準とする。Reader-only修復はRun284/352の段落固定指示を回避する。 |
| Ready Rescue | Run374の既存1-request枠とprovider error時no retry/no fallbackを維持。通常Writerと同じ再試行権限へ拡大しない。 |
| Evidence修復 | Actionに応じた再評価、取得済みEvidenceの収集、Fact/Publication再検証を追跡。Xのraw本文・X/Twitter/t.co redirectはprimary Evidenceに昇格させない。 |
| 最終整形 | Run249の要約生成と、Gate後の`build_clean_note_manuscript` / header再整形で同じ条件を保持する回帰を追加。 |
| Ready / persistence | Quality PASSに加えNotion persistence成功を必要とする既存契約を維持。失敗をReadyとして数えない。 |
| provenance | Run194の最終manuscript bytesに対するbody hashとpolicy hash stamping、lossless transportの既存回帰を維持。 |

これらはコード・fixture・決定論回帰の確認であり、新しい実記事Readyや実Provider可用性を実証したという意味ではない。note DOM/session監査は対象0件という引継ぎ状態のまま未実施で、本監査ではNotion実DBを再照会していない。

## 検証と副作用

- 基準main: **2,726 PASS**。
- 修正後full deterministic regression: **2,736 PASS**（独立レビュー追加のprojection/payload回帰を含む）。
- 既存Pillow `Image.getdata()` deprecation warning: 1。
- Repository-wide Falsification Guard: PASS。
- Integration Stability Guard: PASS。
- current Production Synthetic smoke: **30/30 PASS**, critical failures **0**, `production_write_isolation=true`。
- X回帰はfull regressionに含む。X実装変更なし。
- ローカル初回はSOCKS proxy用`socksio`不足でcollection停止。監査用venvに依存を追加して解消した。Production依存ファイルは変更していない。
- 新policy hash: `895a715ccce4d4acc196678c5bc5ec638919be6856df8a119ad88b7af209be66`。
- Provider/Gemini送信、Daily/ONE-SHOT dispatch、Notion mutation、note mutation、VM起動、公開: すべて0。
- 既存Readyの手動rebase・再認証は行わない。

## main統合時の明示的な副作用

`.github/workflows/note-ready-sync.yml` は `main` の `note_manuscript.py` 更新をpush triggerとして購読し、認証付きで `python note_ready_sync.py` を自動実行する。これはNotion Productionの同期・失効更新を起こし得る。pushではnote draft fan-outは実行されない（manual workflow_dispatch専用）。

本作業の「Notion Production mutationを無断実行しない」制約を守るため、この自動reconciliationを含めた統合可否は、検証済みPRを提示して判断する。既存のreconciliation guardを削除・停止して統合を強行しない。

## 独立レビューで確認した別件

stale Ready selectorのprovenance照会は例外を捕捉するが、下層の`_notion_page_manuscript_blocks`がHTTP 503を空配列へ変換していたため、未知の状態をstaleとして選択する。さらに1ページ目だけを読むため、後続ページのcurrent manuscriptを見落とす。実コードと模擬HTTPによって確認済み。この問題は別ブランチで修正し、要約変更とは分離する。
