# AI Intelligence Factory — Paid Product Contract

更新日: 2026-09-06  
状態: **Run254 current product contract — Work-First / Neutral-Subject Decision Intelligence**

この文書は、有料会員商品に関する現行のSource of Truthです。旧商品説明と矛盾する場合、有料商品のターゲット・見せ方・継続価値については本書を優先します。Evidence / Decision History / Provider budget / Notion access safety等の既存技術契約は変更しません。

## 1. 初期ICP

**Web制作・マーケティング・業務改善・クリエイティブなどでAIを仕事に活用する1〜3名規模の事業者で、ツールを選び、試し、導入判断をする人。**

中心条件は「顧客からAI相談を受けること」ではない。

初期ICPが抱える本筋は、以下。

- AI・ITの変化は知りたい。
- 仕事に何が使えるのか知りたい。
- 何ができるのか、今試す価値があるのか、注意点は何かを理解したい。
- ただし、毎日すべてのニュース・GitHub・公式Docsを追う時間はない。
- AI専業ではないため、Deep Techの全件を日常的に読む必要もない。

顧客への提案・説明は、この判断を必要に応じて仕事へ転用する**副次価値**とする。商品目的そのものへ昇格させない。

「AIに興味がある個人全般」「非エンジニア全般」「法人全般」は初期ICPにしない。法人は将来の高単価市場として維持する。

## 2. 販売する価値

旧1: `AIを調べるためのNotion DB`  
旧2: `顧客からAIの相談をされたときに答えるための商品`

現行: **仕事に関係するAIを理解し、使う・試す・待つ・避けるを判断するためのWork-First Decision Intelligence**

中心メッセージ:

> **AIを全部追わなくても、仕事に使えるものがわかる。**

会員が得るものはDB件数そのものではない。

**知る → 理解する → 仕事に使えるか判断する → 必要なら実際に小さく試す**

までを短時間で進められることを価値とする。

顧客へ説明・提案できることは、この判断能力から派生する応用価値である。

## 3. 日本語表現契約 — Run254

会員向けコピーは**主語省略を基本**とする。

- `自分の仕事に使える` より **`仕事に使える`** を優先する。
- `自分の仕事で知っておく` より **`仕事で知っておく`** を優先する。
- `自分の利用条件` より **`利用条件`** を優先する。
- `自分の作業時間` より **`作業時間`** を優先する。
- `自分の環境` より、文脈に応じ **`利用環境`** を優先する。

`自分` を全面禁止にはしない。`自分だけ / 少人数 / チーム`のように、利用主体の違い自体が意味を持つ場合は残す。

目的は個人向け感を弱めることではなく、**日本語として不要な主語を削り、個人・小規模事業・将来の法人利用にも自然に読める表現へ整えること**である。

## 4. 商品4層

1. **無料note** — 知る・面白く理解する。品質を意図的に落としてPaywallを作らない。
2. **Decision Brief** — 今月、仕事で知っておく価値がある3〜7件だけを短時間で確認する。
3. **Decision Intelligence** — 必要なときに全体DBで比較・根拠・リスク・履歴を確認する。
4. **Work Action Asset** — 使う前の確認、AI活用判断シート、小規模検証条件、比較観点等へ落とす。顧客提案への転用は任意の副次用途。

内部の **Intelligence Engine** は上記より広く、Deep Techを含む。内部追跡対象を会員トップ画面の表示対象と同一視しない。

## 5. DBの位置づけ

- 広いTechnology / Deep Tech inventoryは削除しない。
- DBは商品そのものではなく、商品を支える検索・Evidence・Decision Historyエンジンとする。
- 206件等の件数は信頼の裏付けにはなるが、購入理由として前面に出さない。
- トップ推薦は単純な判断スコア順にしない。
- `実務判断`かつ既存品質条件を満たした中で、**仕事での利用関連性**をNavigation-onlyで評価する。
- `顧客` / `クライアント`という語が入っているだけで上位化しない。顧客文脈は補助シグナルにとどめる。
- Source score / Decision / EvidenceをICP都合で改変しない。

## 6. Work-First表示契約

会員向け詳細では、既存の権威あるフィールドを以下へ翻訳して表示する。

- **仕事で使える場面** — canonical `向いている用途`を基礎とする。
- **仕事への意味（Business Impact）** — canonical判断と判断理由を実務文脈へ翻訳する。根拠のないROI・売上・工数削減率を創作しない。
- **使う前に確認すること** — canonical `主なリスク` / `向いていない用途`を使う。
- **試すときの次の一手** — canonical `次にやること`を利用文脈へ置き換える。
- **Decision Update** — 記録済みmaterial changeが、仕事上の判断を上げる/下げる必要につながるかを示す。

### Production表示の必須条件

本番Notionの自動生成本文は、少なくとも **`いま、どうする？` / `仕事への意味（Business Impact）`** を含み、値が存在する場合は **`仕事で使える場面` / `使う前に確認すること` / `試すときの次の一手`** も含むこと。

Run253前の `案件で使える場面 / 案件への意味 / 提案前に確認すること / 提案時の次の一手` が残っている本文を「現行」と判定してはならない。

Run254以降は、見出しがWork-Firstでも `自分の仕事 / 自分の業務 / 自分の作業 / 自分の利用条件 / 自分の環境` 等の不要な一人称所有表現が残る旧本文を現行扱いしない。表示専用の意味保持置換で一度再構築する。

GitHub Actionsが `python run219_member_human_language_ui.py body` としてCLIファイルを直接実行する本番条件も契約対象とする。Python上で実行中モジュールが `__main__` になっても、current body builderが**実際に実行中のwrapper module**へ結合されなければならない。canonical import側だけを書き換えて成功扱いにしない。

## 7. Decision Update

生の `82 → 91` を継続課金価値の中心にしない。

会員には以下を重視して示す。

- 何が変わったか
- その変化で仕事に使う候補として再検討すべきか
- 慎重になるべきか
- 変化がなく、現在判断を維持してよいか

価格・セキュリティ・保守終了・後継移行・利用条件・実務可能性など、**仕事・費用・使い方の判断に影響する変化**を優先する。

## 8. Work Action Assetの境界

プロンプト集・Makeテンプレート集等を大量配布する「AI素材屋」へピボットしない。

重要な候補についてのみ、必要に応じて以下を付ける。

- 利用目的・条件の確認項目
- 小規模検証の条件
- 使う前チェックリスト
- 比較観点
- 判断メモ1枚
- 再利用可能な最小ワークフロー例

顧客案件へ使う場合は、これらを提案前確認・説明資料へ転用できる。ただし商品を「クライアント提案テンプレートサービス」として定義しない。

## 9. 現行Notion会員面

会員ホームの役割:

- **「AIを全部追わなくても、仕事に使えるものがわかる」**を最初に伝える。
- 3分でDecision Briefへ到達する。
- **仕事で何をしたいか**から候補を見る。
- ADOPT / TEST / WATCH / AVOIDを理解する。
- 必要時のみ全DBへ降りる。
- Decision Updateで判断変更要否を見る。
- Deep Techは補助導線へ下げる。
- AI活用判断シートは利用判断を主用途にし、顧客提案は副次用途とする。

2026年9月Decision Briefの初期構成:

1. Dify
2. AnythingLLM
3. browser-use
4. ComfyUI
5. Cline

これらは固定allowlistではない。将来の候補は同じWork-First関連性契約で自動評価する。

## 10. 価格と商業検証

- 標準価格: **月額1,980円**を維持して検証する。
- 初期検証の目的は「無料なら使う」ではなく、**知らない顧客が自腹/事業経費で1,980円を払うか**を確認すること。
- 初期主要マイルストーン: **実有料顧客10人**。
- 100人獲得はPMF入口を確認した後。

## 11. 集客チャネル

noteは市場そのものではなく、低コストの集客・SEO・信頼形成チャネルの一つ。

商品をnote利用者に最適化しない。必要に応じてGoogle検索、X、YouTube、LinkedIn、Zenn/Qiita、コミュニティ、紹介等へ拡張する。

## 12. 非交渉事項

- Evidence / Fact / Decision品質を商品都合で弱めない。
- Deep Techを削除しない。
- Source scoreを顧客適合度スコアへ置き換えない。
- ICP relevanceは**Navigation-only**。
- 新しい有料APIを追加しない。
- Gemini/model呼出しを表示ロジックに追加しない。
- Public note公開は人間承認のまま。
- Notion schemaはRun254では変更しない。
- 個別ユーザーWatchlist/パーソナライズはPMF前に実装しない。
- CI greenだけを商品改定の完了証明にしない。本番Notion実物の見出し・順位・Source preservationを監査する。
- 「顧客に答えられる」を商品中心へ戻さない。それは副次価値である。
- 不要な `自分の` を商品コピーへ再導入しない。意味上必要な場合だけ使う。

## 13. Run250–254実装契約

- `member_client_action_alignment.py` — 後方互換のファイル名を維持。Run254ではWork-First relevanceに加え、不要な一人称所有表現を表示専用で中立化する。
- `run250_member_client_action_product.py` — Run225後のnavigation overlay + Run219 body overlay。Run251固定shortlist退役、Run252 script-entrypoint authority、Run253 Work-First、Run254 neutral-subject migrationを担当。
- `run219_member_human_language_ui.py` — 既存CLI/authorityを維持した統合入口。
- `tests/test_run250_member_client_action_product.py` — Source score/Evidence/Deep Tech/schema preservation、旧Client Action migration、Work-First relevance、neutral-subject migrationを反証する。

**ZERO model/provider calls.**
