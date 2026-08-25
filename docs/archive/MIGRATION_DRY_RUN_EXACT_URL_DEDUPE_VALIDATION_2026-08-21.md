# Decision Intelligence Migration Dry-run Exact-URL Dedupe Validation — 2026-08-21

## 対象

- 基準ZIP: `AI_Intelligence_Factory_Decision_Intelligence_Phase1_EntityResolution修正版_2026-08-21(2).zip`
- 検証artifact: `decision-intelligence-migration-2-dry-run.zip`
- 元dry-run: `internal_pages=389`, `canonical_entities=389`, `errors=0`

## 発見事項

元artifactでは、同一Product Hunt discovery URLが複数のAMBIGUOUS legacy seedへ分裂していた。
完全一致URLの重複は64行、16グループ。最大6重複。

## 修正ルール

Migration時だけ、以下をすべて満たすAMBIGUOUS legacy rowを1 seedへ統合する。

1. `Source` が完全一致する。
2. `canonicalize_identity_url()` 後の `Primary URL` が完全一致する。
3. URLが空ではない。

統合後もEntity Resolutionは `AMBIGUOUS` のままとし、Technology同一性を推測した扱いにはしない。
タイトル一致だけ、Source違い、意味のあるquery parameter違い、URL違い、空URLは統合しない。

## 実artifact再現検証

修正ロジックへ389 dry-run recordsを再投入した結果:

- Input legacy rows: 389
- Migration entities: 325
- Safely collapsed duplicate rows: 64
- Exact-URL duplicate groups: 16
- 16グループはすべてProduct Hunt
- AMBIGUOUS status: 維持
- Blank/Unknown URL: page-scoped維持

## Regression

- Decision Intelligence tests: 41/41 PASS
- Full unit tests: 303/303 PASS
- Python compileall: PASS
- Synthetic Regression Full: 500/500 PASS
- Synthetic critical failures: 0
- Production writes during local validation: 0

## Apply判定

このコードをGitHubへ反映後、**必ずもう一度GitHub Actionsでdry-runを実行すること**。
次のartifactで `internal_pages=389` 前後に対して `canonical_entities=325` 前後、`errors=0` を確認し、
同一Source＋正規化Primary URL重複が0、Adoption Score/Statusがnull、`LEGACY_PENDING` / `PAUSED` / `Tracking Eligibility=false` を確認してからapplyする。
