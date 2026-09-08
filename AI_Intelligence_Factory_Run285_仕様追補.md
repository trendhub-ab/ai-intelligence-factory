# AI Intelligence Factory Run285 仕様追補

日付: 2026-09-08

## 目的

Run284適用後のCurrent-policy Ready Recovery #3で、Publication安全性ではなく**運用監査の見え方**に2つの欠落が確認された。Run285は品質Gateを変更せず、追加Geminiなしで実態を完全に説明できるようにする。

## Production finding 1: Recovery集計が永続化結果を表せない

Firefox候補ではモデル生成後にQuality Retryが一時障害で尽き、Notionへ`Pending Retry`が保存された。しかし従来controllerは`generate_intelligence_report()`がfalsyを返した時点でcontinueするため、最終集計が次のようになった。

- selected: 1
- generated: 0
- accepted: 0
- recovered: 0
- rejected: 0

`generated`は歴史的に「generatorのtruthy return」を数えるため、その意味自体は変更しない。Run285では以下を追加する。

- `processed`: generator呼び出しが制御フロー上完了した候補数
- `persisted_status_counts`: 呼び出し後に同じNotionページから読み戻したArticle Statusの件数

例:

```text
selected=1
processed=1
generated=0
persisted_status_counts={"Pending Retry": 1}
```

これにより「モデル生成が成功した」と推測せず、永続化された運用結果だけを正確に監査できる。

## Production finding 2: Note Readyの分類合計がReady総数と一致しない

Run284 merge後およびRecovery #3後の実データでは、`source_ready_status_rows=46`に対し、既存分類が以下だった。

- current-policy Ready: 0
- stale publication contract: 40
- incomplete assets: 0
- unsupported source: 5

合計45で1件が説明されていなかった。

原因は、active sourceではあるが`_source_state()`を構成できないReady行（同期ID/タイトル等の必要queue field不足）が無言でcontinueされていたため。

Run285では相互排他的な`invalid_source_state`を追加する。

分類順:

1. unsupported source
2. active sourceだがsource state構築不能 → invalid_source_state
3. stale publication contract
4. incomplete publication assets
5. current-policy Ready

これによりReady総数を分類合計で完全に説明する。

## Firefox Evidence audit

Recovery #3のFirefox記事では、生成稿にApple/Mozilla等が入りFact Gateでunsupported named factとして扱われた。一方、元記事PCWorldにはこれらの記述が存在し、Microsoft/Mozilla公式情報でもブラウザ拡張仕様の方向性を確認できた。

コード監査では、HackerNewsの`external_url`をPrimary URLへ昇格し、取得した本文を`substantive_parts`から`verification_context`へ渡す経路自体は存在することを確認した。しかし既存Productionログには次の実測値が残っていなかった。

- 実際に取得したcontext文字数
- verification context文字数
- evidence document数
- grounding/source method
- primary material取得フラグ

したがってRun285では**Fact Gateを緩和しない**。代わりに、既存`prepare_source_context()`の戻り値をそのまま返す観測wrapperをCurrent-policy Recoveryだけに設置し、上記メタデータをログへ記録する。

重要:
- wrapper自身はHTTP取得を行わない
- `prepare_source_context()`を事前/二重実行しない
- Gemini/model callを追加しない
- Evidence本文をログへ出さない
- Article本文、Gate判定、Retry可否を変更しない

次回Recoveryで初めて、取得不足とGate精度問題を事実ベースで切り分ける。

## 変更しないもの

Run285では以下を変更しない。

- Fact Gate/Hype Gate/Named Fact Gateの閾値
- Reader Value/Human Appeal Gate
- Publication Readiness Gate
- Evidence Sufficiency
- Geminiモデル順序
- Current-policy Recoveryの1候補上限
- model request hard cap 4
- Run284 reader-only repair上限1
- Daily schedule（PAUSED維持）
- private Draft / VM / browser
- public note publication（human-only）

## コスト方針

Run285自体の追加Gemini消費は0。Firefox Recovery #3時点でprovider date 2026-09-07の`gemini-3.6-flash`は16/18まで消費しているため、Run285のCI/merge後もRecovery #4は同provider dayには実行しない。

## 成功条件

- Run285 helperはstdlib-only
- Evidence audit wrapperが元`prepare_source_context()`をexactly onceだけ呼ぶ
- 戻り値identityを保持する
- Note Readyで全Ready source rowが分類される
- Falsy generator + persisted Pending Retryが`processed/persisted_status_counts`へ出る
- historical `generated` semanticsは保持する
- required falsification / full regression / Synthetic Productionがgreen
- merge後はzero-Gemini Note Ready reconciliationのみ実行
