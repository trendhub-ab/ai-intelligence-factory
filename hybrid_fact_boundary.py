"""Deterministic, provider-free Fact Boundary audit for Hybrid Writer output.

This is a high-signal safety net, not a general semantic entailment engine. It rejects
concrete claims that can be checked mechanically against the exact SOURCE CONTEXT shown
to Writer: unsupported numbers/dates/percentages, URLs, technical identifiers, and a
small set of known high-risk factual inflation patterns.
"""
from __future__ import annotations

import re
import unicodedata


class FactBoundaryError(RuntimeError):
    pass


_GENERIC_ASCII_ALLOWLIST = {
    "AI", "IT", "URL", "Web", "note", "SOURCE", "CONTEXT", "Fact",
}

# Narrow semantic families. Each family is a HARD BLOCK only when Writer uses a stronger
# formulation and SOURCE CONTEXT contains no equivalent support phrase from that family.
_HIGH_RISK_RULES = (
    (
        "availability_inflation",
        (
            "誰でも使える", "誰でも利用できる", "誰でもアクセスできる",
            "一般公開されている", "一般公開された", "一般に公開された", "一般提供されている",
            "普通のユーザーでも使える", "一般ユーザーでも使える", "一般ユーザーが使える",
            "通常の利用環境", "通常の対話画面", "普通の対話画面", "一般ユーザー向け設定",
            "製品版の状態", "通常版で使える", "標準設定で使える", "デフォルト設定で使える",
        ),
        (
            "誰でも使える", "誰でも利用できる", "誰でもアクセスできる",
            "一般公開されている", "一般公開された", "一般に公開された", "一般提供されている",
            "普通のユーザーでも使える", "一般ユーザーでも使える", "一般ユーザーが使える",
            "通常の利用環境", "通常の対話画面", "普通の対話画面", "一般ユーザー向け設定",
            "製品版の状態", "通常版で使える", "標準設定で使える", "デフォルト設定で使える",
        ),
    ),
    (
        "contamination_certainty_inflation",
        (
            "混入可能性が極めて低い", "混入の可能性が極めて低い", "混入可能性はほぼない",
            "混入の可能性はほぼない", "混入はほぼ考えにくい", "混入は考えにくい",
            "混入したとは考えにくい", "混入している可能性は低い", "混入していない",
            "データ汚染の可能性は低い", "答えを覚えていた可能性は低い", "答えを覚えていた",
        ),
        (
            "混入可能性が極めて低い", "混入の可能性が極めて低い", "混入可能性はほぼない",
            "混入の可能性はほぼない", "混入はほぼ考えにくい", "混入は考えにくい",
            "混入したとは考えにくい", "混入している可能性は低い", "混入していない",
            "データ汚染の可能性は低い", "答えを覚えていた可能性は低い", "答えを覚えていた",
        ),
    ),
    (
        "zero_day_inflation",
        (
            "誰も発見していなかった", "誰にも発見されていなかった", "これまで誰も見つけていなかった",
            "世界で初めて", "世界初", "初めて発見された", "史上初",
            "未知の不具合", "未知の脆弱性", "未発見の不具合", "未発見の脆弱性",
        ),
        (
            "誰も発見していなかった", "誰にも発見されていなかった", "これまで誰も見つけていなかった",
            "世界で初めて", "世界初", "初めて発見された", "史上初",
            "未知の不具合", "未知の脆弱性", "未発見の不具合", "未発見の脆弱性",
        ),
    ),
    (
        "development_state_inflation",
        (
            "開発中の新しい基盤モデル", "開発中の基盤モデル", "開発段階の基盤モデル",
            "次世代基盤モデル", "次世代の基盤モデル", "未公開の基盤モデル", "試作中の基盤モデル",
        ),
        (
            "開発中の新しい基盤モデル", "開発中の基盤モデル", "開発段階の基盤モデル",
            "次世代基盤モデル", "次世代の基盤モデル", "未公開の基盤モデル", "試作中の基盤モデル",
        ),
    ),
    (
        "evaluation_scope_inflation",
        (
            "本番環境でも同じ結果", "本番環境でも同じ性能", "実運用でも同じ結果", "実運用でも同じ性能",
            "通常環境でも同じ結果", "通常環境でも同じ性能", "一般利用でも同じ結果", "一般利用でも同じ性能",
            "デフォルト環境でも同じ結果", "デフォルト設定でも同じ結果",
        ),
        (
            "本番環境でも同じ結果", "本番環境でも同じ性能", "実運用でも同じ結果", "実運用でも同じ性能",
            "通常環境でも同じ結果", "通常環境でも同じ性能", "一般利用でも同じ結果", "一般利用でも同じ性能",
            "デフォルト環境でも同じ結果", "デフォルト設定でも同じ結果",
        ),
    ),
)

_SAFETY_FUNCTION_RULES = (
    ("refusal_training_function_inference", "拒否訓練", ("不適切な指示を断", "危険な指示を断", "要求を拒否", "危険な要求を拒否", "自動的に拒否")),
    ("classifier_function_inference", "classifier", ("安全性を判定", "危険性を判定", "安全かどうかを判定", "危険かどうかを判定", "安全性を自動判定")),
    ("monitoring_function_inference", "監視", ("ログ収集", "常時判定", "常時監視", "全ユーザーを監視", "行動を追跡", "操作を記録")),
    ("misalignment_function_inference", "misalignment detection", ("AIの意図を読", "意図を検知", "意図を判定", "AIの本音を読", "隠れた意図を検知")),
)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("％", "%")
    return re.sub(r"\s+", " ", value).strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[。！？!?])|\n+", str(text or "")) if s.strip()]


def _number_tokens(text: str) -> set[str]:
    value = _norm(text)
    return set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)*(?:%|年|月|日|件|回|倍|人|個|社|点|歳)?", value))


def _ascii_identifiers(text: str) -> set[str]:
    value = _norm(text)
    pattern = r"(?<![A-Za-z0-9._-])(?=[A-Za-z0-9._-]*[A-Za-z])(?=[A-Za-z0-9._-]*[A-Z0-9])[A-Za-z][A-Za-z0-9._-]{1,}(?![A-Za-z0-9._-])"
    tokens = set(re.findall(pattern, value))
    return {t for t in tokens if t not in _GENERIC_ASCII_ALLOWLIST and not t.startswith(("http", "www"))}


def _urls(text: str) -> set[str]:
    return set(re.findall(r"https?://[^\s)\]}>]+", str(text or "")))


def _violation(kind: str, value: str, article: str, reason: str) -> dict:
    sentence = next((s for s in _sentences(article) if value in _norm(s)), "")
    return {"type": kind, "value": value, "sentence": sentence, "reason": reason}


def audit_fact_boundary(source_context: str, article: str) -> dict:
    source = _norm(source_context)
    output = _norm(article)
    if not source:
        raise FactBoundaryError("fact_boundary_source_context_missing")
    if not output:
        raise FactBoundaryError("fact_boundary_article_missing")

    violations: list[dict] = []

    source_numbers = _number_tokens(source)
    for token in sorted(_number_tokens(output) - source_numbers):
        violations.append(_violation(
            "unsupported_numeric_fact", token, article,
            "Writer introduced a concrete number/date/percentage absent from SOURCE CONTEXT.",
        ))

    source_ids = _ascii_identifiers(source)
    for token in sorted(_ascii_identifiers(output) - source_ids):
        violations.append(_violation(
            "unsupported_technical_identifier", token, article,
            "Writer introduced an ASCII technical/proper identifier absent from SOURCE CONTEXT.",
        ))

    source_urls = _urls(source_context)
    for token in sorted(_urls(article) - source_urls):
        violations.append(_violation(
            "unsupported_url", token, article,
            "Writer introduced a URL absent from SOURCE CONTEXT.",
        ))

    for rule_name, article_phrases, source_support_phrases in _HIGH_RISK_RULES:
        for phrase in article_phrases:
            if phrase in output and not any(support in source for support in source_support_phrases):
                violations.append(_violation(
                    rule_name, phrase, article,
                    "Writer strengthened a factual claim beyond the SOURCE CONTEXT wording.",
                ))

    for rule_name, anchor, inferred_phrases in _SAFETY_FUNCTION_RULES:
        if anchor.lower() not in output.lower():
            continue
        for phrase in inferred_phrases:
            if phrase in output and phrase not in source:
                violations.append(_violation(
                    rule_name, phrase, article,
                    "Writer inferred a safety mechanism function not stated in SOURCE CONTEXT.",
                ))

    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for row in violations:
        key = (row["type"], row["value"])
        if key not in seen:
            seen.add(key)
            unique.append(row)

    return {
        "passed": not unique,
        "violation_count": len(unique),
        "violations": unique,
        "checks": {
            "numeric_fact_delta": True,
            "technical_identifier_delta": True,
            "url_delta": True,
            "known_high_risk_semantic_drift": True,
            "evaluation_scope_inflation": True,
        },
    }


def assert_fact_boundary(source_context: str, article: str) -> dict:
    report = audit_fact_boundary(source_context, article)
    if not report["passed"]:
        kinds = ",".join(sorted({row["type"] for row in report["violations"]}))
        raise FactBoundaryError(f"fact_boundary_failed:{kinds}")
    return report
