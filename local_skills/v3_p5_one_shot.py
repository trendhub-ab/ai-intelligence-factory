"""Full five-stage V3-P5 editorial engine in the canonical ONE-SHOT pipeline.

Baseline: PR #852, commit 95016a65701979063f56130bf181bca831661f5d.
The five distinct staged editorial deliverables are produced in ONE bounded
additional Gemini Deep Dive model call, preserving the original P5 bundled
prompt and stage validator; there is no five-call chain.

The first canonical Production Gemini result supplies only structured management
metadata and Decision/Action. This module replaces its *article* with the
five-stage P5 Fact-Safe Review final manuscript. The existing Production
post-generation Evidence/Fact/Reader/Publication gates remain authoritative.

Fail closed on malformed JSON, incomplete stages, insufficient source evidence,
missing management data, or any provider error. NEVER silently publish the
classic first-pass article if P5 cannot complete.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from .a_plus import build_prewrite_contract
from .v3_p5_contract import (
    EDITORIAL_STAGES,
    Phase0Case,
    validate_article_layout,
    validate_reader_facing_article,
)
from .v3_p5_prompts import build_editorial_bundle_prompt


BASELINE_P5_COMMIT = "95016a65701979063f56130bf181bca831661f5d"
P5_REQUIRED_STAGES = EDITORIAL_STAGES
MAX_NATIVE_CONTEXT_CHARS = 18000
MAX_STRUCTURED_EVIDENCE_CHARS = 16000
ALLOWED_FIRST_CALL_KINDS = frozenset({"deep_dive", "quality_retry"})


class P5EditorialContractError(RuntimeError):
    """P5 must never be replaced by an unreviewed classic article."""


class _ArticleResponse:
    """Preserve original response finish/usage metadata while swapping article text."""

    def __init__(self, original: Any, text: str):
        self._original = original
        self.text = text

    def __getattr__(self, key: str):
        return getattr(self._original, key)


def _extract_bundle(raw: str) -> tuple[str, dict[str, str]]:
    """Parser/validation matching P5's original five-key bundled result."""
    text = str(raw or "").strip()
    if text.startswith("```"):
        at = text.find("\n")
        if at != -1:
            text = text[at + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    try:
        payload = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise P5EditorialContractError("P5 editorial bundle must be valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != set(P5_REQUIRED_STAGES):
        raise P5EditorialContractError("P5 editorial bundle must contain exactly five stages")
    stages = {name: payload[name] for name in P5_REQUIRED_STAGES}
    if not all(isinstance(value, str) and value.strip() for value in stages.values()):
        raise P5EditorialContractError("P5 editorial bundle contains a blank or malformed stage")
    try:
        validate_article_layout(stages["Persona Article Generation"])
        validate_reader_facing_article(stages["Fact-Safe Review"])
    except ValueError as exc:
        raise P5EditorialContractError("P5 final manuscript failed original stage validation") from exc
    return stages["Fact-Safe Review"].strip(), stages


def _source_case(repo: dict, source_info: dict, p: Any) -> Phase0Case:
    """Build an evidence-only Phase0Case; generated management text is NOT facts."""
    result = source_info.get("evidence_result") or {}
    sufficient = (
        source_info.get("evidence_sufficient") is True
        or result.get("state") == getattr(p, "EVIDENCE_SUFFICIENT", "SUFFICIENT")
    )
    if not sufficient:
        raise P5EditorialContractError("P5 requires verified sufficient source evidence")
    native = str(source_info.get("verification_context") or source_info.get("context") or "").strip()
    if len(native) < 80:
        raise P5EditorialContractError("P5 requires nontrivial source-native context")
    metadata = source_info.get("evidence_metadata") or {}
    if not isinstance(metadata, dict):
        raise P5EditorialContractError("P5 evidence metadata is invalid")
    url = str(source_info.get("primary_url") or repo.get("url") or "").strip()
    if not url.startswith(("https://", "http://")):
        raise P5EditorialContractError("P5 requires an explicit primary source URL")

    # Facts come only from the source-native text, never from model-written
    # MANAGEMENT DATA. Bound context to existing Production prompt budgets.
    evidence_text = json.dumps(metadata, ensure_ascii=False, sort_keys=True)[:MAX_STRUCTURED_EVIDENCE_CHARS]
    qualifiers = metadata.get("required_qualifiers") or []
    qualifier_text = " / ".join(map(str, qualifiers))[:3000] if isinstance(qualifiers, list) else ""
    evidence = ("Structured Evidence / Required Qualifiers: " + evidence_text,)
    if qualifier_text:
        evidence += ("Required Qualifiers: " + qualifier_text,)
    return Phase0Case(
        case_id=str(repo.get("name") or url),
        title=str(repo.get("name") or "").strip() or url,
        evidence=evidence,
        facts=(native[:MAX_NATIVE_CONTEXT_CHARS],),
        sources=(url,),
        target_reader="AI導入・事業開発・経営判断・企画判断を行う成人ビジネスパーソン",
    )


def _management_first_pass(first: Any, p: Any) -> tuple[str, dict]:
    raw = str(getattr(first, "text", "") or "")
    token = str(p.SECTION_SPLIT_TOKEN)
    if raw.count(token) != 1 or "=== MANAGEMENT DATA ===" not in raw.split(token, 1)[0]:
        raise P5EditorialContractError("Canonical initial MANAGEMENT DATA output is invalid")
    management = raw.split(token, 1)[0].rstrip()
    parsed = p._parse_gemini_response(raw)
    if not isinstance(parsed, dict) or not all(
        str(parsed.get(key) or "").strip()
        for key in ("title_text", "note_draft", "source_summary_text", "decision_text", "action_text")
    ):
        raise P5EditorialContractError("Canonical management fields are incomplete")
    return management, parsed


def _p5_prompt(case: Phase0Case, parsed: dict, source_info: dict) -> str:
    """Append Production authorities without rewriting the verified five stages."""
    result = dict(source_info.get("evidence_result") or {})
    metadata = dict(source_info.get("evidence_metadata") or {})
    prewrite = build_prewrite_contract(result, metadata)
    management_context = {
        "Source Summary (unverified writer draft, not primary evidence)": parsed.get("source_summary_text", ""),
        "Decision (existing canonical management classification)": parsed["decision_text"],
        "Decision Reason (retain only if grounded)": parsed.get("decision_reason_text", ""),
        "Action (existing canonical management action)": parsed["action_text"],
        "Important: source facts and required qualifiers supersede these management fields": True,
    }
    return (
        build_editorial_bundle_prompt(case).rstrip()
        + "\n\n【Production A+ LocalSkills / Gate Authority｜全5段階で遵守】\n"
        + prewrite
        + "\n以下は既存Productionの構造化管理値。Evidenceではない。"
        + "DecisionとActionの意味だけを維持し、根拠不足の前提・数字を本文へ追加しない。\n"
        + json.dumps(management_context, ensure_ascii=False, sort_keys=True)
        + "\n管理項目はすでに第一工程で生成済み。ここで返すJSONは元のP5仕様と同じ"
        + "5キーのみ。5段階の最終原稿に、管理コード・原稿外の監査コメントを出さない。"
        + "\n公開面の前半「どんな内容？／なぜ重要？／結論は？／元情報」と"
        + "末尾のSources / Evidenceは既存Production組み立て工程が担当する。"
        + "P5のFact-Safe Reviewには重複した要約カードを作らず、筆者の本編を書く。"
        + "既存の前半・後半の出典表示契約は変更しない。"
    )


def _production_article_text(final_article: str) -> str:
    lines = final_article.split("\n", 1)
    if len(lines) != 2 or not lines[0].startswith("# "):
        raise P5EditorialContractError("P5 final H1 title is missing")
    title = lines[0][2:].strip()
    body = lines[1].strip()
    if not title or not body:
        raise P5EditorialContractError("P5 final title/body missing")
    if not title.endswith(("。", "？")):
        title += "。"
    return title + "\n" + body


def apply_p5_editorial_one_shot(
    *,
    p: Any,
    first_response: Any,
    first_grounding: dict,
    canonical_prompt: str,
    repo: dict,
    source_info: dict,
    request_kind: str,
    request_context: str,
    request_origin: str,
    call: Callable[..., tuple],
) -> tuple[Any, dict]:
    """Two provider calls total: Production management, then genuine P5 bundle.

    This is executed only by the existing Production generation call site.
    No standalone production bypass, no additional UI/API credentials, no persist.
    """
    if request_kind not in ALLOWED_FIRST_CALL_KINDS:
        raise P5EditorialContractError("P5 invoked outside permitted Deep Dive contexts")
    if "【A+ Local Skills Pre-Write Contract】" not in canonical_prompt:
        raise P5EditorialContractError("P5 missing required canonical LocalSkills prewrite")
    case = _source_case(repo, source_info, p)
    management, parsed = _management_first_pass(first_response, p)
    bundle_prompt = _p5_prompt(case, parsed, source_info)

    editorial_response, editorial_grounding = call(
        bundle_prompt, repo, source_info,
        request_kind="deep_dive",  # existing per-run/model quota pathway
        request_context=request_context + ":p5_five_stages",
        request_origin=request_origin,
    )
    article, stages = _extract_bundle(getattr(editorial_response, "text", "") or "")
    if tuple(stages) != P5_REQUIRED_STAGES:
        raise P5EditorialContractError("P5 five-stage order drift")
    combined = management + "\n\n" + str(p.SECTION_SPLIT_TOKEN) + "\n" + _production_article_text(article)
    # Verify the same Production parser can read the replacement. The existing
    # Fact/Evidence/Reader/Publication gates then evaluate THIS article normally.
    verified = p._parse_gemini_response(combined)
    if not str(verified.get("note_draft") or "").strip() or not verified.get("decision_text"):
        raise P5EditorialContractError("P5 failed canonical Production parser")
    logger = getattr(p, "logger", None)
    if logger:
        logger.info("[V3 P5 FIVE-STAGE] complete; Production gates unchanged; no standalone publish")
    return _ArticleResponse(editorial_response, combined), editorial_grounding or first_grounding
