# AI Intelligence Factory Run295 仕様追補

## 目的

Run294のproduction read-only監査で、GenRec private draftには620×325pxの大きなヘッダー画像が実在する一方、従来の `画像を変更` selectorが0件となるnote UI変更を確認した。

Run295は、アイキャッチの永続化判定を「旧selectorの有無」から切り離し、private draft作成時と既存draft監査時で同一のfail-closed proofを利用する。

## 確定した不具合

従来の作成側 `note_draft_automation._save_draft_and_verify` は、旧 `画像を変更` controlが存在する場合だけ非表示をエラーにしていた。そのため `count()==0` の場合は、画像が本当に消失していても成功扱いになり得た。

一方Run291監査は旧controlを唯一の存在証拠としていたため、Run294で実在を確認した現行note UIのヘッダー画像をfalse negativeにした。

## Run295 canonical proof

次のいずれかだけをアイキャッチ永続化の肯定証拠とする。

1. 旧 `画像を変更` / `見出し画像を変更` controlが可視。
2. タイトル近傍に幅420px以上・高さ140px以上、natural size 600×200以上の大きな可視画像（または同等のbackground media）があり、可視の `画像を追加` controlが存在しない。

次は肯定証拠にしない。

- 画像系aria-labelの存在だけ。
- file inputの存在だけ。
- 小さなimgだけ。
- タイトルから離れた本文画像だけ。
- DOM取得失敗やgeometry取得不能。

曖昧な場合は必ずfail-closedとする。

## 実装

- `note_eyecatch_persistence.py`
  - DOM count / visibility / geometryだけを収集。
  - image URL/src、DOM HTML、未公開本文を読まない。
  - `classify_eyecatch_persistence()` と `eyecatch_persistence_confirmed()` を共有する。
  - obsolete legacy selectorをshared proofへ橋渡しするPage proxyを提供。
  - canonical draft creationへpostconditionを追加し、旧 `count()==0` escape hatchを閉じる。

- `run194_note_persistent_cloud.py`
  - 現行canonical draft creationにshared creation persistence guardをinstallする。

- `run295_note_private_draft_audit.py`
  - Run292 renderer-faithful body auditを維持しつつ、eyecatchだけshared proofで判定する。
  - 成功時も出力はnon-content metricsのみ。

- `.github/workflows/note-private-draft-audit.yml`
  - live read-only auditをRun295 entrypointへ変更。
  - Run291〜295 contract testsをVM起動前およびself-hosted VM内で実行。
  - audit失敗時もVM停止を必須維持。

## 安全境界

Run295は以下を変更しない。

- Publication Contract
- Ready manuscript bytes
- article generation prompt / model routing
- Gemini quota
- note public release
- existing private draft content
- Notion human workflow state

read-only監査側にはclick/fill/upload/save/screenshot/network write/publication/model callを追加しない。

作成側は既存のprivate draft creation時にのみ適用され、既存のtitle/body persistence gateを弱めない。shared eyecatch proofが取れなければqueue rowを進めない。

## Production検証条件

Run295 merge後、既存GenRec private draftを1回だけ再監査する。

期待値:

- status: `audit_passed`
- `eyecatch_present=true`
- `eyecatch_proof_mode=eyecatch_present_header_media`
- zero Gemini calls: true
- read_only: true
- draft_mutation: false
- public_release: false
- VM stop: success

この条件を満たしても自動公開は行わない。
