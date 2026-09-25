# Fixed Evidence: saved run and offline reader counterfactual (2026-09-25)

## Live run already completed

- GitHub Actions run: 36125338613, attempt 2, branch head be58004c.
- Evidence: astral-sh/uv README at dd965a276182e2d46d80439feecd03216cc6643a; frozen Evidence hash 16671659452346c263177ecaa0e1b81fd5efb21271264d7b91407ac7f50266a6.
- Provider-visible attempts: 3. gemini-3.6-flash returned 503 once; gemini-3.5-flash returned 200 for initial and feedback drafts. The campaign ledger has one earlier reserved slot and three from this run: cumulative 4/4. No further sends are permitted on that campaign.
- Initial draft: Fact failed (high-risk action, hype, performance multiplier scope); Publication REVIEW (score/narrative); Reader Value WEAK.
- Feedback draft: Publication PASS, but Fact failed on performance multiplier scope; Reader Value WEAK. Ready-eligible count 0. No note/Notion writes.

## Verified rescue defect

The performance qualifier rescue previously mistook “環境を再現する…異なるツール” for a sentence about variable performance. Its broad variability regex skipped the required qualifier even though the stricter Fact Gate rejected the multiplier. The PR change aligns the rescue's variability check with the existing Fact Gate. The saved initial and feedback drafts each gain one qualifier with all numeric lexemes unchanged; the feedback draft then passes Fact. Reader Value remains WEAK, so the saved model output is still ineligible for Ready.

## Offline counterfactual: article body only

The note draft below was edited by a human-facing analysis step, not produced by Gemini. It reuses the saved feedback response's management fields and frozen Evidence. The production parser, polish and Gates were run on the replacement body without a provider request or persistence.

| Gate | Result |
| --- | --- |
| Evidence | SUFFICIENT |
| Fact | PASS, no reasons |
| Editorial | PASS, soft warning: missing observation or reservation |
| Publication | PASS |
| Reader Value | ACCEPTABLE, no reasons |
| Disposition | PASS_WITH_WARNINGS; Ready-eligible before persistence |

### Counterfactual note body

Pythonの環境づくりは「速さ」だけで選べるか。uvを小さく試す理由

Pythonで新しい仕事を始めると、コードを書く前に環境づくりが待っています。言語の版をそろえ、必要な部品を入れ、次に開いても同じ状態を再現する。uvは、Pythonで使う部品（ライブラリ）の導入や開発環境の準備をまとめて担う道具です。これまで別々の道具に任せていた作業を、一つにまとめようとしています。

公式の説明では、uvはPythonの版や依存関係の管理、環境の作成、ロックファイルによる再現、スクリプトの実行を扱います。Rustで作られ、macOS、Linux、Windowsに対応します。これだけ機能が並ぶと、今の道具を丸ごと替えたくなるかもしれません。

そこで一度立ち止まりたいのが、「pipより10〜100倍高速」という開発元の主張です。これは開発元が示すベンチマーク条件での数字です。実際の改善幅は処理内容、ネットワークや実行環境によって変わります。手元の仕事が同じ速さになると確認されたわけではありません。

さらに、既存の複雑なプロジェクトを完全に移行できる保証も、この一次情報からは読み取れません。速さの期待と、移行時に確かめるべきことは分けて考えたほうがいいでしょう。

私なら、まず影響の小さな社内ツールでuvを試します。次に既存プロジェクトのコピーを使い、今の道具と同じ部品を入れて時間と生成物を比べます。そこで効果と互換性を確かめてから、採用範囲を決めます。全面移行を急ぐより、小さな比較で自分の環境に合うかを判断する段階です。

## Interpretation and limits

This single article proves that the currently installed Gates can jointly accept a body using the same uv Evidence and management fields. It does not show that Gemini 3.7/3.8 can produce this body, establish a model Ready rate, or cause a Notion Ready transition. A future bounded model test must retain the four-slot campaign's audit history and verify a new quota-safe reservation path for its model before any send. Model-generated drafts should be judged for factual fidelity and reader access; no Evidence, Fact, or Publication thresholds were changed here.
