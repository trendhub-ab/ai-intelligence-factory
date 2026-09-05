# Run236 — Evidence Context Modularization

## Purpose

`pipeline.py`の肥大化を、品質・Evidence・Decision・Gemini quota・Notion永続化を変えずに段階的に解消する。

Run236は、一次情報本文の文字数制御だけを対象とする。対象はprovider/API/DBに依存しない決定論的ロジックであり、Production挙動を変更する機能追加ではない。

## Extracted canonical module

`evidence_context.py`

Canonical ownership:

- `truncate_text_context(text, max_chars)`
- `verification_excerpt(text, max_chars)`
- `merge_verification_context(existing, new_evidence, max_chars)`

`pipeline.py`には既存signatureを保つ薄いbinding wrapperだけを残す。

- `_truncate_source_context(text)` → current `SOURCE_CONTEXT_MAX_CHARS`
- `_truncate_verification_context(text)` → current `VERIFICATION_CONTEXT_MAX_CHARS`
- `_merge_verification_context(existing, new_evidence)` → current `VERIFICATION_CONTEXT_MAX_CHARS`

これにより、テストやoperatorがpipeline側の上限値を一時変更する既存契約も維持する。

## Preserved behavior

- 3行以上の空行は2行へ正規化する。
- verification本文が上限を超える場合、冒頭68%・末尾32%相当を残す。
- markerは`[...verification context omitted...]`を維持する。
- 新Evidence結合時は、新Evidenceへ最大60%の監査枠を優先する。
- 片側が短い場合、余剰枠をもう片側へ戻す。
- 文字数上限が64以下の場合の単純先頭truncateを維持する。

## Non-goals / protected contracts

Run236では以下を変更しない。

- Gemini model / fallback順
- RPD / RPM / TPM / retry budget / pacing
- Screening / Deep Dive件数
- Fact / Evidence / Decision Score / Publication / Human Appeal gate
- Evidence authority / entity binding
- Notion schema / write path
- note publication contract
- Daily PAUSED
- Public note human-only release

## Historical migration test isolation

Run236で`_truncate_text_context`を`pipeline.py`から正当に物理削除した結果、Run235 Stage3Bのhistorical migration testが、Run235自身の責務ではない「現在の`pipeline.py`に`def _truncate_text_context`が存在すること」を要求していたため失敗した。

これはProduction不具合ではなく、後続リファクタリングに耐えないstale historical test contractだった。

Run236ではRun235の責務を次のように再固定する。

- Run235が現在も保証するもの: source normalization 6関数の重複定義が`pipeline.py`へ復活していないこと、`source_normalization.py`がcanonical ownerであること、migrationがcurrent canonical postimageに対してidempotentであること。
- Run235当時だけのsurgical proof: `tests/fixtures/run235_stage3b_pipeline_preimage.py.txt`を固定preimageとして使用し、migration outputとcommitted patchのforward/reverse round-tripを検証する。
- Run235 testは、後続Runで変化し得る現在の`pipeline.py`隣接実装をhistorical preimage再構成の材料にしない。
- `_truncate_text_context`の現在の所在はRun236の責務であり、Run235のcontractから除外する。

この分離により、後続Runが`pipeline.py`の隣接領域を正当に抽出しても、過去Runのhistorical migration testが誤ってブロックしない。

## Falsification contract

`tests/test_run236_evidence_context_module.py`で以下を検証する。

1. 新moduleにprovider/Notion/GitHub network surfaceがない。
2. `evidence_context.py`が3つのpure algorithmのcanonical ownerである。
3. truncateのexact parity。
4. verification excerptのexact parity。
5. pipeline側の動的`SOURCE_CONTEXT_MAX_CHARS`を維持。
6. pipeline側の動的`VERIFICATION_CONTEXT_MAX_CHARS`を維持。
7. merge wrapperがlive `VERIFICATION_CONTEXT_MAX_CHARS`を参照しhistorical behaviorを維持。
8. 重いmerge/excerptロジックが`pipeline.py`から物理削除され、pipelineには薄いlimit-bindingだけが残る。

Run236専用testと`evidence_context.py` compileは、Repository-wide Falsification GuardとIntegration Reconciliation CIの双方で名指し実行する。Integration CIではfull pytestとSynthetic smokeも引き続き実行する。

## Rollback

Run236はstrangler extractionであり、rollback時も品質条件を緩めない。必要なら新moduleの3関数を元の`pipeline.py`へ戻せるが、Decision/Evidence/Gemini/Notion契約は変更しない。
