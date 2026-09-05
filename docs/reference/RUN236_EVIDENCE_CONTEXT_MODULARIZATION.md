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

## Falsification contract

`tests/test_run236_evidence_context_module.py`で以下を検証する。

1. 新moduleにprovider/Notion/GitHub network surfaceがない。
2. truncateのexact parity。
3. verification excerptのexact parity。
4. pipeline側の動的`SOURCE_CONTEXT_MAX_CHARS`を維持。
5. pipeline側の動的`VERIFICATION_CONTEXT_MAX_CHARS`を維持。
6. mergeのhistorical behaviorを維持。
7. 重いmerge/excerptロジックが`pipeline.py`から物理削除され、新moduleがcanonical ownerになる。

## Rollback

Run236はstrangler extractionであり、rollback時も品質条件を緩めない。必要なら新moduleの3関数を元の`pipeline.py`へ戻せるが、Decision/Evidence/Gemini/Notion契約は変更しない。
