"""Run223 technical-claim precision guardrails.

Closes five narrow issues exposed by the first full human audit of a real note draft:
- operation-specific parameters must not be collapsed into one generic setting;
- selected/partial breaking changes must not become total prohibitions;
- multiplier/performance claims must preserve source modality and workload limits;
- source publication dates must come from explicit primary-source metadata, never ingestion/analysis dates;
- a tiny high-precision Japanese typo gate catches malformed particles before publication.

The layer is zero-API. It strengthens generation guidance, Fact Gate validation and local retry
instructions without changing Evidence thresholds, Decision scoring, API budgets or reader style.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_INSTALLED_ATTR = "_run223_technical_claim_precision_installed"

_MULTIPLIER_RE = re.compile(r"(?<![0-9.])(\d+(?:\.\d+)?)\s*(?:倍|x\s+(?:faster|speedup))", re.I)
_SPEED_RE = re.compile(r"(?:高速|速(?:い|く|さ)|速度|性能|performance|faster|speedup)", re.I)
_EXPECTATION_RE = re.compile(r"(?:expect(?:ed|s|ation)?|estimate|estimated|benchmark|measurement|measured|trial|example|期待|見込|試算|ベンチマーク|測定|計測|例)", re.I)
_ARTICLE_SCOPE_RE = re.compile(r"(?:チーム|公式|一次情報|期待|見込|試算|ベンチマーク|測定|条件|処理内容|実行環境|ワークロード|場合|によって|依存|team|official|source|expect|benchmark|condition|workload|depend)", re.I)
_VARIABILITY_RE = re.compile(r"(?:実際[^。！？\n]{0,35}(?:変わ|異な)|(?:処理内容|実行環境|条件|ワークロード)[^。！？\n]{0,35}(?:変わ|異な|依存)|(?:var(?:y|ies)|depend)[^.?!\n]{0,40}(?:workload|condition|environment))", re.I)

_BROAD_CONVERSION_RE = re.compile(
    r"(?:暗黙(?:的)?|曖昧)[^。！？\n]{0,40}型変換[^。！？\n]{0,28}(?:禁止|全面(?:的に)?廃止|すべて廃止|許さない)",
    re.I,
)
_CONVERSION_QUALIFIER_RE = re.compile(r"(?:一部|特定|場合|情報[^。！？\n]{0,20}失われ|lossy|selected|some|certain)", re.I)

_MAINTAIN_TRUE_RE = re.compile(r"maintain_order\s*=\s*True", re.I)
_MAINTAIN_LEFT_RE = re.compile(r"maintain_order\s*=\s*[\"']left[\"']", re.I)
_JOIN_RE = re.compile(r"\bjoin\b", re.I)
_GROUP_BY_RE = re.compile(r"\bgroup_by\b", re.I)

_MALFORMED_JA_PATTERNS = (
    re.compile(r"によるな(?:処理|性能|速度|効果|改善)", re.I),
)

_DATE_LINE_RE = re.compile(r"(?:公開・更新|公開日|一次情報(?:の)?公開日)\s*[:：]\s*(\d{4}-\d{2}-\d{2})")
_PRIMARY_DATE_KEYS = {
    "primary_source_published_at",
    "primary_source_published_date",
    "primary_published_at",
    "primary_published_date",
    "source_published_at",
    "source_published_date",
    "first_party_published_at",
    "first_party_published_date",
    "datepublished",
}


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", str(text or "")) if part.strip()]


def _local_window(text: str, start: int, end: int, radius: int = 220) -> str:
    value = str(text or "")
    return value[max(0, start - radius): min(len(value), end + radius)]


def multiplier_scope_failures(article: str, source_context: str) -> list[str]:
    """Reject strong x-times speed claims when expectation/benchmark scope is lost."""
    source = str(source_context or "")
    failures: list[str] = []
    for match in _MULTIPLIER_RE.finditer(str(article or "")):
        local = _local_window(article, match.start(), match.end())
        if not _SPEED_RE.search(local):
            continue
        number = match.group(1)
        source_mentions = re.search(rf"(?<![0-9.]){re.escape(number)}\s*(?:x|倍)", source, re.I)
        if not source_mentions:
            continue
        source_local = _local_window(source, source_mentions.start(), source_mentions.end(), 280)
        if not _EXPECTATION_RE.search(source_local):
            continue
        if not _ARTICLE_SCOPE_RE.search(local) or not _VARIABILITY_RE.search(str(article or "")):
            failures.append(
                "performance_multiplier_scope_lost: a source expectation/benchmark multiplier is presented "
                "without preserving attribution/modality and workload-or-condition variability"
            )
            break
    return failures


def broad_conversion_failures(article: str) -> list[str]:
    """Catch only explicit total-prohibition wording around implicit/ambiguous type conversion."""
    failures: list[str] = []
    for match in _BROAD_CONVERSION_RE.finditer(str(article or "")):
        sentence = _local_window(article, match.start(), match.end(), 90)
        if _CONVERSION_QUALIFIER_RE.search(sentence):
            continue
        failures.append(
            "conversion_scope_overgeneralized: selected/possibly-lossy conversion strictness is written as a blanket prohibition"
        )
        break
    return failures


def operation_parameter_failures(article: str, source_context: str) -> list[str]:
    """High-precision guard for collapsing method-specific maintain_order values."""
    source = str(source_context or "")
    if not (_MAINTAIN_TRUE_RE.search(source) and _MAINTAIN_LEFT_RE.search(source)):
        return []
    for paragraph in _paragraphs(article):
        if not (_JOIN_RE.search(paragraph) and _GROUP_BY_RE.search(paragraph)):
            continue
        if _MAINTAIN_TRUE_RE.search(paragraph) and not _MAINTAIN_LEFT_RE.search(paragraph):
            return [
                "operation_specific_parameter_collapsed: join and group_by are discussed together but distinct maintain_order values from primary evidence are collapsed"
            ]
    return []


def malformed_japanese_failures(article: str) -> list[str]:
    for pattern in _MALFORMED_JA_PATTERNS:
        match = pattern.search(str(article or ""))
        if match:
            return [f"malformed_japanese_particle: obvious malformed phrase remains ({match.group(0)})"]
    return []


def _parse_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("start", "date", "value"):
            if key in value:
                parsed = _parse_date(value.get(key))
                if parsed:
                    return parsed
        return ""
    text = str(value).strip()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if not match:
        return ""
    try:
        datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return ""
    return match.group(1)


def _collect_primary_dates(value: Any, *, parent_key: str = "") -> set[str]:
    dates: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized in _PRIMARY_DATE_KEYS:
                parsed = _parse_date(child)
                if parsed:
                    dates.add(parsed)
            dates.update(_collect_primary_dates(child, parent_key=normalized))
    elif isinstance(value, (list, tuple)):
        for child in value:
            dates.update(_collect_primary_dates(child, parent_key=parent_key))
    return dates


def source_date_failures(
    article: str,
    evidence_metadata: dict | None = None,
    source_info: dict | None = None,
    freshness: dict | None = None,
) -> list[str]:
    """Compare only against explicitly named primary/source publication metadata.

    Generic `date`, ingestion timestamps, analysis dates and crawl dates are intentionally ignored.
    If there is no single authoritative first-party date, this validator stays silent and the prompt
    tells the model to omit rather than guess.
    """
    match = _DATE_LINE_RE.search(str(article or ""))
    if not match:
        return []
    dates: set[str] = set()
    for payload in (evidence_metadata, source_info, freshness):
        dates.update(_collect_primary_dates(payload or {}))
    if len(dates) != 1:
        return []
    expected = next(iter(dates))
    actual = match.group(1)
    if actual == expected:
        return []
    return [
        f"primary_source_date_mismatch: article date {actual} does not match explicit primary-source publication date {expected}"
    ]


def technical_claim_failures(
    parsed: dict,
    source_context: str,
    *,
    evidence_metadata: dict | None = None,
    source_info: dict | None = None,
    freshness: dict | None = None,
) -> list[str]:
    article = str((parsed or {}).get("note_draft") or "")
    failures: list[str] = []
    failures.extend(operation_parameter_failures(article, source_context))
    failures.extend(broad_conversion_failures(article))
    failures.extend(multiplier_scope_failures(article, source_context))
    failures.extend(source_date_failures(article, evidence_metadata, source_info, freshness))
    failures.extend(malformed_japanese_failures(article))
    return list(dict.fromkeys(failures))[:10]


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_prompt = pipeline_module.build_decision_prompt
    original_validate_fact = pipeline_module.validate_fact_gate
    original_build_retry = pipeline_module.build_dynamic_retry_instruction

    def build_prompt_with_technical_precision(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        return prompt.rstrip() + (
            "\n\n【技術Claim精度 / Run223】\n"
            "・同じパラメータ名でもAPI/メソッドごとに許容値や意味が違う場合、1つの設定値へ丸めないでください。"
            "一次資料にある操作ごとの正確な呼び出しを分けて示し、コピー可能なコードは特に厳密にしてください。\n"
            "・一次資料が一部・特定ケース・lossyな変換の厳格化を述べているだけなら、『暗黙変換を禁止』『全面廃止』へ一般化しないでください。"
            "対象範囲を『一部』『情報が失われる可能性のある場合』など資料の境界に合わせてください。\n"
            "・x倍、%改善、レイテンシ等が期待値・ベンチマーク・例示なら、そのモダリティと主体を保持してください。"
            "『チームは〜と期待』『公式ベンチマークでは』のように書き、実際の改善幅が処理内容・条件・環境で変わる場合はその留保も落とさないでください。\n"
            "・『公開・更新』等の一次情報の日付は、一次サイト本文/明示的first-party metadataだけを使ってください。"
            "収集日、Hacker News投稿日、分析日、Notion保存日を一次情報の公開日に代用してはいけません。確認不能なら日付を省略してください。\n"
            "・最終稿では助詞欠落や『によるな処理』のような明白な日本語崩れを残さないでください。\n"
        )

    def validate_fact_with_technical_precision(
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
        extra = technical_claim_failures(
            parsed,
            source_context,
            evidence_metadata=evidence_metadata,
            source_info=source_info,
            freshness=freshness,
        )
        merged = list(dict.fromkeys(list(failures or []) + extra))[:20]
        if extra:
            pipeline_module.logger.warning("[RUN223 TECHNICAL CLAIM] failures=%s repo=%s", extra, repo_name)
        return (bool(ok) and not extra), merged

    def build_retry_with_technical_precision(reason_rows: list[dict]):
        instruction, sections = original_build_retry(reason_rows)
        messages = "\n".join(str((row or {}).get("message") or "") for row in (reason_rows or []))
        additions: list[str] = []
        if "operation_specific_parameter_collapsed:" in messages:
            additions.append("・操作固有パラメータは該当段落だけを修正し、一次資料どおりにメソッド別の値を分けてください。新しいAPI値を推測しないでください。")
        if "conversion_scope_overgeneralized:" in messages:
            additions.append("・型変換の厳格化は該当文だけを修正し、『一部』『lossy/情報損失の可能性がある場合』等、一次資料の対象範囲へ戻してください。全面禁止へ拡張しないでください。")
        if "performance_multiplier_scope_lost:" in messages:
            additions.append("・倍率/性能値は該当文だけを修正し、期待/測定/ベンチマークの主体と条件を復元し、実際の改善幅が処理内容や環境で変わる留保を残してください。")
        if "primary_source_date_mismatch:" in messages:
            additions.append("・一次情報の日付だけを正してください。明示的first-party publication dateを使い、収集日・分析日・発見元投稿日を代用しないでください。")
        if "malformed_japanese_particle:" in messages:
            additions.append("・日本語の明白な助詞崩れだけを局所修正し、Fact/Decision/Evidenceを変更しないでください。")
        if additions:
            instruction = instruction.rstrip() + "\n【Run223 Technical Claim Patch】\n" + "\n".join(additions) + "\n"
        return instruction, sections

    pipeline_module.build_decision_prompt = build_prompt_with_technical_precision
    pipeline_module.validate_fact_gate = validate_fact_with_technical_precision
    pipeline_module.build_dynamic_retry_instruction = build_retry_with_technical_precision
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
