# AI Intelligence Factory — Paid Product Contract

更新日: 2026-09-06
状態: **Run252 current product contract**

この文書は、有料会員商品に関する現行のSource of Truthです。`REVENUE_PRODUCT_PHASE2_SETUP.md`等の旧商品説明と矛盾する場合、有料商品のターゲット・見せ方・継続価値については本書を優先します。Evidence / Decision History / Provider budget / Notion access safety等の既存技術契約は変更しません。

## 1. 初期ICP

**Web制作・マーケティング・業務改善などを受託する1〜3名規模の事業者で、顧客からAI活用を相談されるようになったが、AI専業ではない人。**

「AIに興味がある個人全般」「非エンジニア全般」「法人全般」を初期ICPにしない。

法人は将来の高単価市場として維持するが、初期PMF検証では請求書・稟議・セキュリティ審査等の販売摩擦を持ち込まない。

## 2. 販売する価値

旧: `AIを調べるためのNotion DB`

現行: **クライアントにAIを提案・判断するときに使える実務インテリジェンス**

中心メッセージ:

> **AIの相談をされたとき、答えに困らない。**

会員が得るものはDB件数そのものではない。顧客案件について、根拠を持って **使う / 試す / 待つ / 避ける** を判断し、次の一手まで説明できることを価値とする。

## 3. 商品4層

1. **無料note** — 知る・理解する。品質を意図的に落としてPaywallを作らない。
2. **Decision Brief** — 今月、初期ICPが先に見るべき3〜7件だけを短時間で確認する。
3. **Decision Intelligence** — 必要なときに全体DBで比較・根拠・リスク・履歴を確認する。
4. **Client Action Asset** — 顧客への質問、導入判断シート、検証条件、提案前チェック等へ落とす。

内部の **Intelligence Engine** は上記より広く、Deep Techを含む。内部追跡対象を顧客トップ画面の表示対象と同一視しない。

## 4. DBの位置づけ

- 広いTechnology / Deep Tech inventoryは削除しない。
- DBは商品そのものではなく、商品を支える検索・Evidence・Decision Historyエンジンとする。
- 206件等の件数は信頼の裏付けにはなるが、購入理由として前面に出さない。
- トップ推薦は単純な判断スコア順にしない。
- `実務判断`かつADOPT/TEST等の既存品質条件を満たした中で、初期ICPへの業務関連性をNavigation-onlyで評価する。
- Source score / Decision / EvidenceをICP都合で改変しない。

## 5. Client Action表示契約

会員向け詳細では、既存の権威あるフィールドを以下へ翻訳して表示する。

- **案件で使える場面** — canonical `向いている用途`を基礎とする。
- **案件への意味（Business Impact）** — canonical判断と判断理由を案件文脈へ翻訳する。根拠のないROI・売上・工数削減率を創作しない。
- **提案前に確認すること** — canonical `主なリスク` / `向いていない用途`を使う。
- **提案時の次の一手** — canonical `次にやること`を案件向け表現へ置き換える。
- **Decision Update** — 記録済みのmaterial changeが、案件判断を上げる/下げる必要につながるかを示す。

### Production表示の必須条件

本番Notionの自動生成本文は、少なくとも **`いま、どうする？` / `案件への意味（Business Impact）`** を含み、値が存在する場合は **`案件で使える場面` / `提案前に確認すること` / `提案時の次の一手`** も含むこと。

旧Run219本文がSource値の一致だけで「現行」と判定されることを禁止する。本文一致判定はClient Action見出しまで検証する。

さらに、GitHub Actionsが `python run219_member_human_language_ui.py body` としてCLIファイルを直接実行する本番条件を正式な契約対象とする。Python上で実行中モジュールが `__main__` になっても、Run250/252のClient Action body builderが**実際に実行中のwrapper module**へ結合されなければならない。canonical import側だけを書き換えて成功扱いにしない。

## 6. Decision Update

生の `82 → 91` を継続課金価値の中心にしない。

会員には以下を重視して示す。

- 何が変わったか
- その変化で案件候補として再検討すべきか
- 慎重になるべきか
- 変化がなく、現在判断を維持してよいか

価格・セキュリティ・保守終了・後継移行・利用条件・実務可能性など、**仕事・費用・提案内容に影響する変化**を優先する。

## 7. Action Assetの境界

プロンプト集・Makeテンプレート集等を大量配布する「AI素材屋」へピボットしない。

重要な候補についてのみ、必要に応じて以下を付ける。

- 顧客への確認項目
- 小規模検証の条件
- 提案前チェックリスト
- 比較観点
- 説明用1枚シート
- 再利用可能な最小ワークフロー例

テンプレート保守が商品原価を押し上げないよう、Evidenceに基づき重要なものへ限定する。

## 8. 現行Notion会員面

会員ホームの役割:

- 3分でDecision Briefへ到達
- 顧客の相談内容から候補を見る
- ADOPT / TEST / WATCH / AVOIDを理解する
- 必要時のみ全DBへ降りる
- Decision Updateで判断変更要否を見る
- Deep Techは補助導線へ下げる

2026年9月Decision Briefの初期構成:

1. Dify
2. AnythingLLM
3. browser-use
4. ComfyUI
5. Cline

これらは固定allowlistではない。将来の候補は同じICP関連性契約で自動評価する。

本番ホームの「注目順位」は旧固定3件を優先しない。Run251以降、Navigation-only ICP relevance + 既存quality/lifecycle contractが最終選定権限を持つ。

## 9. 価格と商業検証

- 標準価格: **月額1,980円**を維持して検証する。
- 初期検証の目的は「無料なら使う」ではなく、**知らない顧客が自腹/事業経費で1,980円を払うか**を確認すること。
- 初期主要マイルストーン: **実有料顧客10人**。
- 100人獲得はPMF入口を確認した後。
- 価格を先に下げて、ターゲット不一致・商品不一致・価格不一致を混同しない。

## 10. 集客チャネル

noteは市場そのものではなく、低コストの集客・SEO・信頼形成チャネルの一つ。

商品をnote利用者に最適化しない。必要に応じてGoogle検索、X、YouTube、LinkedIn、Zenn/Qiita、コミュニティ、紹介等へ拡張する。

## 11. 非交渉事項

- Evidence / Fact / Decision品質を商品都合で弱めない。
- Deep Techを削除しない。
- Source scoreを顧客適合度スコアへ置き換えない。
- ICP relevanceは**Navigation-only**。
- 新しい有料APIを追加しない。
- Gemini/model呼出しをRun250/252表示ロジックに追加しない。
- Public note公開は人間承認のまま。
- Notion schemaはRun250/252では変更しない。
- 個別ユーザーWatchlist/パーソナライズはPMF前に実装しない。
- CI greenだけを商品改定の完了証明にしない。本番Notion実物の見出し・順位・Source preservationを監査する。

## 12. Run250–252実装契約

- `member_client_action_alignment.py` — ICP関連性とAction表示のpure deterministic policy
- `run250_member_client_action_product.py` — Run225後のnavigation overlay + Run219 body overlay。Run251で旧固定shortlistをretireし、Run252でscript-entrypoint body authorityを追加。
- `run219_member_human_language_ui.py` — 既存CLI/authorityを維持した統合入口。body実行時は `sys.modules[__name__]` をRun250へ渡し、`__main__` 実行でもactive wrapperへClient Action builderを結合する。
- `tests/test_run250_member_client_action_product.py` — Source score/Evidence/Deep Tech/schema preservation、旧shortlist、stale body、script-entrypoint authorityの反証契約。

**ZERO model/provider calls.**
