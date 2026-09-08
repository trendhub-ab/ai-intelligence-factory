# AI Intelligence Factory Run293 仕様追補

## 目的
Run292で本文比較の期待値生成をnote貼付時と同一レンダラへ統一した後も、既存GenRec private draftのread-only監査は `non_body_guard_failed` でFail-Closedした。
Run293は監査Gateを緩めず、固定された非本文エラーだけを安全なカテゴリコードへ変換し、どの実画面Gateが停止理由かを未公開本文・タイトル・draft URLを露出せず特定可能にする。

## 変更範囲
- `run292_note_rendered_body_audit.py` に固定エラー→allow-list診断コードのマッピングを追加。
- 未知エラーは必ず `non_body_guard_failed` のままFail-Closed。
- `note-private-draft-audit.yml` のpreflight/live回帰にRun293反証テストを追加。
- Repository-wide Falsification GuardにRun293反証テストを追加。

## 例となる診断コード
- `note_auth_inactive`
- `editor_route_invalid`
- `draft_title_mismatch`
- `semantic_structure_read_failed`
- `body_h1_present`
- `heading_structure_lost`
- `eyecatch_persistence_unconfirmed`
- `editor_geometry_unavailable`
- `editor_width_narrow`
- `chrome_history_no_routes`
- `draft_not_matched_from_history`

## 安全境界
Run293は以下を変更しない。
- Gemini/model API呼び出し: 0
- draft作成・保存・編集: 0
- note公開: 0
- screenshot/artifactへの未公開内容保存: 0
- Publication Contract: 変更なし
- Fact/Reader/Publication Gate: 緩和なし
- Daily: 変更なし

診断結果にはallow-listコード、既存の数値・真偽値メトリクス、ハッシュ化済みroute識別子以外の未公開本文情報を含めない。

## 反証条件
1. 既知の固定Run291エラーが期待するカテゴリコードへ変換される。
2. 未知例外文にprivate routeや未公開情報が含まれても結果へコピーされない。
3. mutation / screenshot / model / public-release surfaceを追加していない。
4. VMは監査成否にかかわらず従来どおり`always()`経路で停止する。
5. Run292のrenderer-faithful本文比較Gateはそのまま維持する。

## 次工程
Run293をCIで反証後にmainへmergeし、GenRec既存private draftへread-only監査を1回だけ再実行する。
診断コードが記事内容・表示構造側の修復を要求する場合のみ、その原因に対して最小修正を行う。Gemini APIは必要性が確定した場合に限り使用し、監査原因の特定目的では消費しない。
