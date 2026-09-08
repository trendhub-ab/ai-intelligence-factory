# AI Intelligence Factory Run294 仕様追補

## 背景
Run293の既存GenRec private draft実画面監査により、停止点は本文ではなく `eyecatch_persistence_unconfirmed` と確定した。

さらに作成側 `note_draft_automation._save_draft_and_verify()` を反証すると、旧アイキャッチ検証は「`画像を変更`系ボタンが存在するときだけ非表示を失敗にする」条件であり、対象ボタンが0件の場合はFail-Closedしていなかった。このため、実際の画像欠落とnote UI selector driftの双方を区別する必要がある。

## 目的
既存private draftを一切変更せず、アイキャッチ周辺のDOM構造から次を安全に分類する。

1. 大きなヘッダーメディアが存在し、旧selectorだけ見つからない → `eyecatch_present_selector_drift_likely`
2. ヘッダーメディアがなく、画像追加UIが見える → `eyecatch_missing_likely`
3. 証拠不足 → ambiguous系コードのままFail-Closed

## 観測する情報
未公開コンテンツではなく、以下の数値・真偽値のみ。
- 旧アイキャッチ変更controlの件数/可視件数
- 画像系aria-label controlの件数/可視件数
- 画像追加controlの件数/可視件数
- file input件数
- visible img件数
- title近傍の大きなimg件数
- title近傍の大きなCSS background-image要素件数
- visible picture件数
- 最大候補mediaの表示幅/高さ
- viewport幅/高さ
- title geometry取得可否

## 明示的に取得・出力しないもの
- img src / currentSrc / image URL
- DOM innerHTML / outerHTML
- unpublished title/body/manuscript
- private draft URL
- screenshot
- browser storage state

## 安全境界
- Gemini/model calls: 0
- draft mutation: 0
- public release: 0
- screenshot: 0
- Publication Contract: 変更なし
- Fact/Reader/Publication Gate: 緩和なし
- Daily: 変更なし/PAUSED
- 監査成否にかかわらずVM停止は既存`always()`経路を維持

## 次工程
Run294をrequired CIで反証しmainへmerge後、GenRec既存private draftをread-onlyで1回だけ再監査する。

- selector drift likelyなら、実画面証拠に基づきアイキャッチ永続化判定helperを修正し、作成側と監査側を同じ判定へ統一する。
- missing likelyなら、既存Ready sourceのアイキャッチを用いた「アイキャッチのみ修復」workflowを設計する。タイトル/本文は前後fingerprintで不変を保証し、公開操作は行わない。
- API/modelは既存アイキャッチ資産が利用不能な場合のみ検討し、診断目的では消費しない。
