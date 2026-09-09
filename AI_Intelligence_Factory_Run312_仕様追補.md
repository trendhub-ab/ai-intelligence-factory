# AI Intelligence Factory Run312 仕様追補

Run312は、ユーザーが手動更新した公開固定note `ned673e381ef8` を自動上書きせず、実ページ本文をread-onlyで取得してcurrent Product Contractと再照合する監査層である。

## 追加仕様

- Run309 exact-target auditの対象ID・read-only契約を維持する。
- `body_text` / `body_sha256` / `body_links` を監査結果へ追加する。
- 取得した本文はRun307 product positioning、Run217 commerce fulfillmentおよびcurrent superseding member contractsと照合する。
- 実態と異なる表現があった場合のみ、手動修正版を尊重した最小修正を別途行う。
- Run310の旧ready-to-paste本文を機械的に再適用しない。

## 不変条件

- Note mutation 0
- Gemini/model 0
- Notion write 0
- Production ONE-SHOT 0
- Scheduled Daily PAUSED維持
