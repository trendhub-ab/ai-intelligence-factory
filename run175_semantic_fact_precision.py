"""Run175 semantic fact precision guardrails.

Targets two narrow failure modes observed in the 2026-09-01 production Daily audit:
1. semantic category drift such as calling a similarity/distance score a probability,
2. turning a benchmark/example performance number into an unqualified general claim.

The layer is deliberately high-precision and zero-API. It strengthens generation guidance,
Fact Gate validation, and patch-retry instructions without changing Evidence thresholds,
Decision scoring, article style, or Gemini request budgets.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_INSTALLED_ATTR = "_run175_semantic_fact_precision_installed"

_PROBABILITY_SIMILARITY_PATTERNS = (
    re.compile(r"確率的(?:な)?\s*(?:類似度|距離|スコア)", re.I),
    re.compile(r"(?:類似度|距離|コサイン類似度|埋め込み(?:の)?スコア)[^。！？\n]{0,28}(?:確率(?:的)?|確率値)", re.I),
    re.compile(r"\bprobabilistic\s+(?:similarity|distance|similarity\s+score)\b", re.I),
    re.compile(r"\b(?:similarity|distance|cosine\s+similarity|embedding\s+score)\b[^.?!\n]{0,36}\bprobabilit(?:y|istic)\b", re.I),
)

_SOURCE_EXPLICIT_PROBABILITY_SIMILARITY_PATTERNS = (
    re.compile(r"確率的(?:な)?\s*(?:類似度|距離|スコア)", re.I),
    re.compile(r"(?:確率|probability)[^。！？\n]{0,24}(?:として解釈|に変換|calibrat|normalized)[^。！？\n]{0,30}(?:類似度|距離|similarity|distance)", re.I),
    re.compile(r"\bprobabilistic\s+(?:similarity|distance|similarity\s+score)\b", re.I),
    re.compile(r"\bprobability[- ]based\s+(?:similarity|distance)\b", re.I),
)

# Do not use Unicode \w boundaries here. In Japanese prose a latency value is often
# attached directly to a particle (e.g. "待たずに4ミリ秒で"), and Japanese letters are
# Unicode word characters. We only exclude adjacent ASCII numeric/identifier characters.
_PERFORMANCE_NUMBER_RE = re.compile(
    r"(?<![0-9A-Za-z.])(\d+(?:\.\d+)?)\s*(ms|msec|milliseconds?|ミリ秒|s|sec|seconds?|秒)(?![0-9A-Za-z])",
    re.I,
)

_TITLE_SCOPE_QUALIFIER_RE = re.compile(
    r"(?:公式(?:の)?(?:例|比較|測定|ベンチマーク)|ベンチマーク|測定|計測|テスト|検証|実験|公開例|比較例|"
    r"この(?:環境|条件|測定|検証|例)|特定(?:の)?(?:環境|条件)|example|benchmark|measured|measurement|test|experiment)",
    re.I,
)

_BENCHMARK_CONTEXT_RE = re.compile(
    r"(?:benchmark|measured|measurement|test|evaluation|experiment|example|comparison|compare|versus|\bvs\.?\b|"
    r"figure|time[- ]to[- ]first[- ]token|decision\s+time|ベンチマーク|測定|計測|テスト|評価|実験|例|比較|対比|公開値)",
    re.I,
)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).replace("×", "x")
    return re.sub(r"\s+", " ", value).strip()


def _markdown_title(article: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", str(article or ""), re.MULTILINE)
    return match.group(1).strip() if match else ""


def _source_explicitly_probabilistic(source_context: str) -> bool:
    text = _norm(source_context)
    return any(pattern.search(text) for pattern in _SOURCE_EXPLICIT_PROBABILITY_SIMILARITY_PATTERNS)


def semantic_category_failures(article: str, source_context: str) -> list[str]:
    """Catch only explicit probability↔similarity category conflation unsupported by source."""
    text = _norm(article)
    if not text:
        return []
    if _source_explicitly_probabilistic(source_context):
        return []
    for pattern in _PROBABILITY_SIMILARITY_PATTERNS:
        match = pattern.search(text)
        if match:
            snippet = match.group(0)[:80]
            return [
                "semantic_category_mismatch: similarity/distance score is described as probability/probabilistic "
                f"without matching primary-evidence terminology ({snippet})"
            ]
    return []


def _number_unit_variants(number: str, unit: str) -> tuple[str, ...]:
    n = _norm(number).lower()
    u = _norm(unit).lower()
    if u in {"ms", "msec", "millisecond", "milliseconds", "ミリ秒"}:
        units = ("ms", "msec", "millisecond", "milliseconds", "ミリ秒")
    elif u in {"s", "sec", "second", "seconds", "秒"}:
        units = ("s", "sec", "second", "seconds", "秒")
    else:
        units = (u,)
    return tuple(f"{n}{x}" for x in units) + tuple(f"{n} {x}" for x in units)


def _local_source_windows(source_context: str, number: str, unit: str, radius: int = 260) -> list[str]:
    source = _norm(source_context)
    compact = source.lower()
    windows: list[str] = []
    variants = _number_unit_variants(number, unit)
    for variant in variants:
        start = 0
        while True:
            pos = compact.find(variant.lower(), start)
            if pos < 0:
                break
            windows.append(source[max(0, pos - radius): min(len(source), pos + len(variant) + radius)])
            start = pos + max(1, len(variant))
    return windows


def benchmark_scope_failures(article: str, source_context: str) -> list[str]:
    """Reject unqualified title latency claims only when evidence presents that value as an example/comparison."""
    title = _markdown_title(article)
    if not title or _TITLE_SCOPE_QUALIFIER_RE.search(title):
        return []
    failures: list[str] = []
    for match in _PERFORMANCE_NUMBER_RE.finditer(_norm(title)):
        number, unit = match.group(1), match.group(2)
        windows = _local_source_windows(source_context, number, unit)
        if not windows:
            continue
        if not any(_BENCHMARK_CONTEXT_RE.search(window) for window in windows):
            continue
        token = match.group(0)
        failures.append(
            "benchmark_scope_overgeneralized: title uses "
            f"{token} as an unqualified general performance claim although the evidence presents that value "
            "in a benchmark/example/comparison context"
        )
    return list(dict.fromkeys(failures))[:4]


def semantic_fact_failures(parsed: dict, source_context: str) -> list[str]:
    article = str((parsed or {}).get("note_draft") or "")
    failures: list[str] = []
    failures.extend(semantic_category_failures(article, source_context))
    failures.extend(benchmark_scope_failures(article, source_context))
    return list(dict.fromkeys(failures))[:8]


def install(pipeline_module: Any) -> Any:
    """Install Run175 guardrails idempotently on top of the current production stack."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_prompt = pipeline_module.build_decision_prompt
    original_validate_fact = pipeline_module.validate_fact_gate
    original_build_retry = pipeline_module.build_dynamic_retry_instruction

    def build_prompt_with_semantic_precision(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        return prompt.rstrip() + (
            "\n\n【意味精度とベンチマーク境界 / Run175】\n"
            "・embedding / cosine similarity / distance / similarity scoreは、連続値であるだけでは確率ではありません。"
            "一次資料がprobability/probabilisticとして明示的に定義・校正していない限り、『確率』『確率的な類似度』と呼ばず、"
            "『類似度』『距離』『スコア』『閾値』など資料の語彙に合わせてください。\n"
            "・ms、秒などの性能値がベンチマーク、比較例、特定条件での測定値なら、タイトル・導入・結論でも条件を落とさないでください。"
            "『公式例では』『ベンチマークでは』『この測定では』のように範囲を明示し、単一測定を一般的な保証・常時性能へ拡張しないでください。\n"
            "・一次資料が条件を明示していない場合は、数値を強い一般化へ使わず、限定表現または数値なしの表現を優先してください。\n"
        )

    def validate_fact_with_semantic_precision(
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
        extra = semantic_fact_failures(parsed, source_context)
        merged = list(dict.fromkeys(list(failures or []) + extra))[:16]
        if extra:
            pipeline_module.logger.warning("[RUN175 SEMANTIC FACT] failures=%s repo=%s", extra, repo_name)
        return (bool(ok) and not extra), merged

    def build_retry_with_semantic_precision(reason_rows: list[dict]):
        instruction, sections = original_build_retry(reason_rows)
        messages = "\n".join(str((row or {}).get("message") or "") for row in (reason_rows or []))
        additions: list[str] = []
        if "semantic_category_mismatch:" in messages:
            additions.append(
                "・semantic_category_mismatchは該当文だけを局所修正してください。一次資料が確率と明示していない場合、"
                "probability/確率という分類を削除し、資料にあるsimilarity/distance/score/thresholdの語彙へ戻してください。"
                "新しい理論説明や数値を足さないでください。"
            )
        if "benchmark_scope_overgeneralized:" in messages:
            additions.append(
                "・benchmark_scope_overgeneralizedはタイトルまたは該当文だけを局所修正してください。数値が資料のbenchmark/example/比較値なら、"
                "『公式例では』『ベンチマークでは』『この測定では』等で範囲を復元してください。根拠が一致している数値自体は不要に変更せず、"
                "保証表現へ拡張しないでください。"
            )
        if additions:
            instruction = instruction.rstrip() + "\n【Run175 Semantic Fact Patch】\n" + "\n".join(additions) + "\n"
        return instruction, sections

    pipeline_module.build_decision_prompt = build_prompt_with_semantic_precision
    pipeline_module.validate_fact_gate = validate_fact_with_semantic_precision
    pipeline_module.build_dynamic_retry_instruction = build_retry_with_semantic_precision
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
