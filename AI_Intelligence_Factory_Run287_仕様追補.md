# AI Intelligence Factory Run287 仕様追補

## 背景

Current-policy Ready Recovery #4で、Netflix TechBlog「GenRec」が初めてcurrent-policy Readyへ到達した。

公開前の人間監査で、記事ヘッダーに次の表示を確認した。

- `公開・更新: 2026-08-15`

しかしHacker News取得コードを追跡すると、Hacker News item APIの `time` を `published_at` として正規化し、その値が外部一次記事の `公開・更新` として表示されていた。

したがって、この日付は外部一次記事の公開日ではなくHacker News側の投稿日・発見時刻である。一次記事の公開日を示すEvidenceにはならない。

## Run287の変更

Hacker News由来の候補については、既存 `published_at` を一次記事の `公開・更新` として表示しない。

代わりに日付が存在する場合は次のように表示する。

- `Hacker News投稿日: YYYY-MM-DD`

主一次情報URLと発見経路は従来どおり維持する。

一次記事自身の公開日を取得できていない場合、モデル知識や推測で補完しない。

## 非変更

- Fact Gate
- Reader Value / Human Appeal Gate
- Publication Readiness
- Evidence Sufficiency
- Gemini model routing
- Gemini request budget
- 記事本文生成prompt
- Eyecatch生成
- Daily PAUSED
- private draft / public publication boundary

## Publication Contract

Run287は読者が見る公開原稿のmetadata bytesを変更するため、`run287_publication_date_provenance.py` をPublication Contract fingerprintへ含める。

したがってmerge後は既存Readyが一度staleになることを正しい挙動とする。新しいpolicy SHAで再検証されたReadyだけをnote投稿候補へ戻す。

## コスト判断

原因はモデルではなく決定論的metadata provenanceであるため、修正・unit test・CIではGemini APIを使わない。

Run287 merge後の実Production再検証でのみ、必要最小限のCurrent-policy Ready Recoveryを使う。Recovery #4では3.7を1回使用し、3.6は未使用だったため、ユーザー申告の3.6残り2回は温存されている。
