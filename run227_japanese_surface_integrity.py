"""Run227 high-precision Japanese surface-integrity guard.

A real Run226 FULL ONE-SHOT produced two manuscripts that passed every existing gate but still
contained obvious broken Japanese (for example ``結果はでした。`` and ``計算はに速くなる``).
The same audit also exposed a narrow lexical/grammar misuse (``FP4を過度に適応すると``).
This zero-model layer blocks only narrow, high-confidence surface corruption before Ready.

It does not rewrite prose deterministically because the missing predicate/adverb or intended
lexeme cannot be reconstructed safely without changing meaning. Instead it adds a local Fact Gate
failure and a retry instruction so the normal bounded generation/retry path can repair the
sentence. Fact, Evidence, Decision, score, source URLs and API budgets are unchanged.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALLED_ATTR = "_run227_japanese_surface_integrity_installed"

# Remove code before scanning. Broken prose inside code examples/identifiers is not a publication
# grammar defect and should not create false positives.
_FENCED_CODE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Predicate-less topic + copula. These nouns cannot naturally terminate as 「Xはです/でした」.
_EMPTY_PREDICATE_RE = re.compile(
    r"(?:結果|結論|答え|原因|理由|ポイント|要点)は(?:です|でした)(?=[。！？!?\s]|$)"
)

# High-confidence particle collision observed in Production. Restrict the following stem to
# comparative/change vocabulary so ordinary strings such as 「Aは日本語で」 never match.
_HA_NI_COLLISION_RE = re.compile(
    r"はに(?=(?:速|遅|高|低|大|小|強|弱|増|減|変|近|遠|広|狭|長|短|重|軽))"
)

# 「適応する」 is intransitive in this editorial context. Run #24 emitted
# 「FP4を過度に適応すると」 where the intended operation was 適用. Keep the object vocabulary
# deliberately technical/narrow and do not match the valid causative 「適応させる」 or
# 「モデルが環境に適応する」.
_TECH_OBJECT_ADAPT_RE = re.compile(
    r"(?:FP4|FP8|BF16|量子化|精度|設定|方式|ルール|機能|API|パッチ|変更)を"
    r"(?:過度に|そのまま|直接|全面的に)?適応(?=(?:する|した|して|すると))"
)


def _prose_only(text: str) -> str:
    value = _FENCED_CODE_RE.sub("", str(text or ""))
    return _INLINE_CODE_RE.sub("", value)


def japanese_surface_failures(article: str) -> list[str]:
    prose = _prose_only(article)
    for pattern, reason in (
        (_EMPTY_PREDICATE_RE, "predicate_missing"),
        (_HA_NI_COLLISION_RE, "particle_collision_ha_ni"),
        (_TECH_OBJECT_ADAPT_RE, "transitivity_adapt_vs_apply"),
    ):
        match = pattern.search(prose)
        if match:
            return [
                f"malformed_japanese_surface:{reason}: obvious broken Japanese remains ({match.group(0)})"
            ]
    return []


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_prompt = pipeline_module.build_decision_prompt
    original_validate_fact = pipeline_module.validate_fact_gate
    original_build_retry = pipeline_module.build_dynamic_retry_instruction

    def build_prompt_with_surface_integrity(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        marker = "【日本語Surface Integrity / Run227】"
        if marker in prompt:
            return prompt
        return prompt.rstrip() + (
            "\n\n【日本語Surface Integrity / Run227】\n"
            "・最終稿を提出する前に、各文を日本語として読み直してください。『結果はでした。』のように述語が欠けた文、"
            "『〜はに速くなる』のような助詞衝突、技術を『〜を適応する』のように不自然な他動詞として扱う表現を残してはいけません。\n"
            "・意味を補うために新しいFact・数値・人物・因果を作らず、SOURCE BOUNDARY内の内容だけで自然な日本語へ整えてください。\n"
        )

    def validate_fact_with_surface_integrity(
        parsed: dict,
        repo_name: str,
        source_context: str = "",
        source: str = "",
        evidence_metadata: dict | None = None,
        source_info: dict | None = None,
        freshness: dict | None = None,
        output_truncated: bool = False,
    ):
        ok, failures = original_validate_fact(
            parsed,
            repo_name,
            source_context=source_context,
            source=source,
            evidence_metadata=evidence_metadata,
            source_info=source_info,
            freshness=freshness,
            output_truncated=output_truncated,
        )
        article = str((parsed or {}).get("note_draft") or "")
        extra = japanese_surface_failures(article)
        merged = list(dict.fromkeys(list(failures or []) + extra))[:20]
        if extra:
            pipeline_module.logger.warning("[RUN227 JAPANESE SURFACE] failures=%s repo=%s", extra, repo_name)
        return (bool(ok) and not extra), merged

    def build_retry_with_surface_integrity(reason_rows: list[dict]):
        instruction, sections = original_build_retry(reason_rows)
        messages = "\n".join(str((row or {}).get("message") or "") for row in (reason_rows or []))
        if "malformed_japanese_surface:" not in messages:
            return instruction, sections
        addition = (
            "・日本語Surface Integrity: 指摘された壊れた1文だけを、元のFact/Evidence/Decisionを変えず自然な日本語へ局所修正してください。"
            "欠けた内容や意図語を推測して新しい数値・人物・因果を足してはいけません。"
        )
        return instruction.rstrip() + "\n" + addition + "\n", sections

    pipeline_module.build_decision_prompt = build_prompt_with_surface_integrity
    pipeline_module.validate_fact_gate = validate_fact_with_surface_integrity
    pipeline_module.build_dynamic_retry_instruction = build_retry_with_surface_integrity
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
