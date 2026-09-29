"""Run-scoped adapter from current Production structured fields to Local Skills.

This module is canary-only. It does not write to Notion, publish to note, call a
provider, or alter Gate policy. The Gemini Deep Dive may still produce its normal
structured management fields; every provider-generated article surface is
discarded before the frozen provider-free compiler renders the article.

Current Free Article management data intentionally does not require the legacy
Main Risk / Best For / Avoid For fields. The deterministic completeness adapter
below fills only those publication helper slots when absent. Its fallbacks add no
source facts, names, numbers, performance claims, or outcomes.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .compiler import compile_snapshot


def _text(value: Any) -> str:
    return str(value or "").strip()


def _evidence_urls(primary_url: str, grounding: Mapping[str, Any] | None) -> list[str]:
    values: list[str] = []
    for value in list((grounding or {}).get("evidence_urls") or []):
        url = _text(value)
        if url and url not in values:
            values.append(url)
    primary = _text(primary_url)
    if primary and primary not in values:
        values.append(primary)
    return values


def _deterministic_reader_title(name: str) -> str:
    """Build an article title without reusing provider-generated article prose."""
    topic = re.sub(r"^Show HN:\s*", "", name, flags=re.I).strip()
    topic = re.sub(r"\s+[–—-]\s+My attempt at\b.*$", "", topic, flags=re.I).strip()
    return f"{topic}：いま何を判断材料にするべきか"


_ADOPTION_ACTION_RE = re.compile(
    r"導入|採用|利用|使(?:う|える)|試(?:す|用)|PoC|概念実証|本番|実装|移行|運用|展開",
    re.I,
)
_OBSERVATIONAL_ACTION_RE = re.compile(
    r"確認|比較|評価|追跡|基準点|点検|調査|参照|照合|記録|レビュー|監視|再評価|見直",
    re.I,
)
_NON_ADOPTABLE_TOPIC_RE = re.compile(
    r"設立|創業|発足|宣言|判決|訴訟|事件|攻撃|漏洩|流出|事故|制度|規制|法案|歴史|当時|"
    r"報告書|公表|発表内容|研究結果|ベンチマーク結果",
    re.I,
)


def _management_is_observational(parsed: Mapping[str, Any]) -> bool:
    action = _text(parsed.get("action_text"))
    if _OBSERVATIONAL_ACTION_RE.search(action) and not _ADOPTION_ACTION_RE.search(action):
        return True
    if _ADOPTION_ACTION_RE.search(action):
        return False
    surface = " ".join(
        _text(parsed.get(key))
        for key in (
            "source_summary_text", "what_text", "why_important_text",
            "decision_reason_text",
        )
    )
    return bool(_NON_ADOPTABLE_TOPIC_RE.search(surface))


def _completion_boundary(parsed: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Fill Local Writer publication-helper slots without inventing source facts.

    Only management-only parser fields may supply article-specific values.
    Article-body fallback fields (why_not_important_text / who_should_use_text /
    who_should_not_use_text) are deliberately ignored because the provider article
    must not leak into the Local Skills fresh measurement.
    """
    decision = _text(parsed.get("decision_text")).upper()

    values = {
        "primary_risk": _text(parsed.get("main_risk_text")),
        "best_for": _text(parsed.get("best_for_text")),
        "avoid_for": _text(parsed.get("avoid_for_text")),
    }
    sources = {
        key: ("management_data" if value else "deterministic_publication_boundary")
        for key, value in values.items()
    }

    observational = _management_is_observational(parsed)

    if not values["primary_risk"]:
        values["primary_risk"] = (
            "一次情報の対象範囲を越えて一般化せず、確認済みの事実と未確認の部分を分ける必要があります。"
            if observational
            else "一次情報の対象範囲を越えて一般化せず、限定した検証で条件差を確認する必要があります。"
        )

    if not values["best_for"]:
        if observational:
            values["best_for"] = "一次情報を基準点として残し、追加情報で判断を更新できるチーム。"
        elif decision in {"NOW", "TRY"}:
            values["best_for"] = "一次情報の範囲を守り、小さな検証から判断材料を増やせるチーム。"
        elif decision in {"WATCH", "WAIT"}:
            values["best_for"] = "導入を急がず、条件の変化を確認して再評価できるチーム。"
        elif decision == "AVOID":
            values["best_for"] = "採用を広げず、代替案を比較しながら判断を維持できるチーム。"
        else:
            values["best_for"] = "一次情報の範囲を守り、限定した条件で検証できるチーム。"

    if not values["avoid_for"]:
        if observational:
            values["avoid_for"] = "一つの情報だけで結論を固定し、追加確認を行わないチーム。"
        elif decision in {"WATCH", "WAIT", "AVOID"}:
            values["avoid_for"] = "追加確認を待たず、すぐ本番適用を前提にしたいチーム。"
        else:
            values["avoid_for"] = "検証条件を確認せず、結果を広く一般化して本番適用したいチーム。"

    return values, sources


def build_snapshot(
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source: str,
    primary_url: str,
    grounding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    name = _text(repo.get("nameWithOwner") or repo.get("name"))
    entity_url = _text(repo.get("primaryUrl") or primary_url or repo.get("url"))
    seed = f"{source}|{entity_url}|{name}"
    completion, _sources = _completion_boundary(parsed)
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32],
        "canonical_entity_id": _text(repo.get("canonical_entity_id")) or f"url:{entity_url}",
        "name": name,
        "reader_title": _deterministic_reader_title(name),
        "source": _text(source),
        "source_summary": _text(parsed.get("source_summary_text")),
        "what": _text(parsed.get("what_text")),
        "why_important": _text(parsed.get("why_important_text")),
        "decision": _text(parsed.get("decision_text")).upper(),
        "decision_score": int(parsed.get("score") or 0),
        "decision_reason": _text(parsed.get("decision_reason_text")),
        "action": _text(parsed.get("action_text")),
        "primary_risk": completion["primary_risk"],
        "best_for": completion["best_for"],
        "avoid_for": completion["avoid_for"],
        "evidence_urls": _evidence_urls(primary_url, grounding),
    }


def apply_to_production_parsed(
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source: str,
    primary_url: str,
    grounding: Mapping[str, Any] | None,
    evidence_context: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    completion, completion_sources = _completion_boundary(parsed)
    snapshot = build_snapshot(
        repo, parsed, source=source, primary_url=primary_url, grounding=grounding
    )
    compiled = compile_snapshot(snapshot, evidence_context=evidence_context)
    out = dict(parsed)
    # The canary must send one internally-consistent Local Skills surface to every Gate.
    # Previously only title/note_draft were replaced, so Human Appeal could inspect the
    # stale provider action_text while the visible article contained the canonicalized
    # Local Skills action. Synchronize every compiler-owned reader/decision field.
    out.update(dict(compiled["parsed"]))
    # The canonical manuscript builder owns the complete Sources / Evidence footer,
    # including rights provenance and the article disclaimer. Keeping this short
    # Writer footer ahead of the CTA makes later CTA normalization drop that block.
    body, marker, _footer = str(out.get("note_draft") or "").rpartition("\n### Sources / Evidence")
    if marker:
        out["note_draft"] = body.rstrip() + "\n"
    meta = {
        "status": compiled["status"],
        "case_id": snapshot["case_id"],
        "canonical_entity_id": snapshot["canonical_entity_id"],
        "canonicalizer_version": compiled["canonicalizer_version"],
        "canonicalizer_blob_sha": compiled["canonicalizer_blob_sha"],
        "writer_blob_sha": compiled["writer_blob_sha"],
        "evidence_boundary_version": compiled["evidence_boundary_version"],
        "removed_unsupported_numeric_claims": int(
            compiled["evidence_boundary"].get("removed_count", 0)
        ),
        "source": snapshot["source"],
        "evidence_url_count": len(snapshot["evidence_urls"]),
        "provider_article_surface_reused": False,
        "deterministic_title": True,
        "compiled_structured_surface_synced": True,
        "completeness_adapter_sources": dict(completion_sources),
        "completeness_adapter_fallback_fields": sorted(
            key for key, value in completion_sources.items()
            if value == "deterministic_publication_boundary"
        ),
    }
    # Keep the exact completion values out of metadata to avoid duplicating
    # reader-facing prose; tests assert that they contain no provider article leak.
    assert completion == {
        "primary_risk": snapshot["primary_risk"],
        "best_for": snapshot["best_for"],
        "avoid_for": snapshot["avoid_for"],
    }
    out["_local_skills_canary"] = dict(meta)
    return out, meta
