"""Run275/276/351/397 zero-API reader-quality precision overlay.

Real ONE-SHOT Run31 produced three evidence-sufficient manuscripts but Ready=0. Artifact
falsification showed two different causes mixed together: genuine dense technical prose and
narrow reader diagnostics that could misclassify valid reader bridges, visible heading breaks,
or later acronym explanations. Run32 then exposed one more precision defect: the historical
7-character repetition detector could classify recurring topic nouns (for example the Japanese
equivalents of "the agent" / "all data") as repeated *insight*.

Run351 uses the real Run38 DeepSeek manuscript as an additional precision case. It corrects
only three reproducible false-positive surfaces: A4/MIT when used as ordinary compound labels,
a low-density business-decision opening that is plainly reader-relevant, and a bounded set of
proper-name-heavy paragraphs inside an otherwise low-density, bridged, well-sectioned article.

Run397 redefines Reader accessibility around Decision Intelligence. Technical vocabulary is not
itself a publication defect. A specialist article may keep decision-relevant terminology when the
reader can still understand what changed, why it matters, the important capability/limitation, and
what action to take. Topic-adaptive plainness only affects density diagnostics; Fact, Evidence,
Japanese integrity, unexplained required terms, and decision/limitation fidelity are never relaxed.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALL_FLAG = "_run275_reader_quality_precision_installed"
READER_VALUE_MARKER = "reader_value_review:"

_PULL_MARKERS_RE = re.compile(
    r"(?:[？?]|たとえば|例えば|もし|ところが|一方|逆に|意外|実際|場面|朝\d{0,2}時|困る|怖い|変わる|比べ|なのに)"
)
_STRONG_OPENING_BRIDGE_RE = re.compile(
    r"(?:[？?]|でしょうか|ませんか|ありますか|ありますよね|ですよね|"
    r"たとえば|例えば|もし|スマホ|買い物|旅行|学校|家族|仕事で|使う側|"
    r"普通の言葉|簡単に言えば|要するに|意外|困った|迷った|"
    r"(?:あなた|私たち)[^。！？]{0,90}(?:不安|困|迷|課題|悩|障壁|懸念|選択|使|導入)|"
    r"自社[^。！？]{0,120}(?:業務|プロダクト|導入|運用|コスト|費用|判断|検証)|"
    r"意思決定者[^。！？]{0,100}(?:悩|判断|選択|検討|決め))"
)
_GA_NI_COLLISION_RE = re.compile(
    r"がに(?=(?:減少|増加|向上|低下|改善|悪化|変化)(?:し|する|した|します|しました))"
)
_REPETITION_PREDICATE_RE = re.compile(
    r"(?:です|ます|した|して|する|され|でき|ない|なる|なり|ある|あり|いる|"
    r"べき|必要|重要|可能|難し|高止まり|減衰|収縮|改善|悪化|増加|減少|変化|"
    r"超え|引き継|選ぶ|選択|試す|検証|導入|見送|待つ|推奨|勧め|価値)"
)

_SPECIALIST_TOPIC_RE = re.compile(
    r"(?:arXiv|論文|数理|定理|証明|モデル構造|アーキテクチャ|認証|認可|セキュリティ|"
    r"暗号|脆弱性|攻撃|DPoP|OAuth|OIDC|microVM|仮想化|RAG|MCP|ベンチマーク)",
    re.I,
)
_DEVELOPER_TOPIC_RE = re.compile(
    r"(?:OSS|オープンソース|GitHub|SDK|CLI|API|ライブラリ|フレームワーク|"
    r"開発ツール|開発者|パッケージ|リポジトリ|データベース|インフラ|Kubernetes)",
    re.I,
)
_DECISION_BRIDGE_RE = re.compile(
    r"(?:なぜ重要|重要なのは|意味する|何が変わ|変わるのは|影響|判断|"
    r"私なら|使うなら|導入するなら|試す|比較|待つ|見送|採用|検証)"
)
_CAPABILITY_LIMIT_RE = re.compile(
    r"(?:できる|可能|対応|使える|向いて|ただし|一方で|制約|限界|未検証|"
    r"できない|難しい|保証|対象外|注意|リスク)"
)
_ACTION_RE = re.compile(
    r"(?:私なら|導入するなら|使うなら|まず[^。！？]{0,80}(?:試|比較|確認|検証)|"
    r"試す|比較する|比較します|待つ|待ち|見送る|見送ります|採用|導入|検証する|検証します)"
)

DECISION_ACCESSIBILITY_CONTRACT = r"""
【Decision Accessibility Contract｜専門性を残したまま判断可能にする】
この記事の目標は「非専門家が全文を専門家と同じ深さで理解すること」ではなく、
「非専門家でも核心と意思決定を理解できること」です。既存のReader指示と衝突する場合は、
Fact/Evidence/Publication安全を除き、この契約を平易さ・専門語処理の上位原則として扱います。

1. 冒頭と結論は、専門知識がなくても「何の話か／なぜ重要か／何ができる・できないか／
   自分なら試す・比較する・待つ・見送るのどれか」が分かるようにする。
2. 本文ではDecisionや重要制約を変える専門語を普通に使ってよい。初出時に、その語の役割を
   同じEvidenceの範囲で短い1文または括弧書きで説明する。専門語を消すための長い比喩は不要。
3. Evidence、仕様、正式名称、数値、論文上の用語は専門的なままでよい。正確性を落としてまで
   日常語へ完全置換しない。
4. 比喩・会話句・身近な例は任意。Gateを通すためだけに追加しない。説明を足し続けて本文を
   長くするより、Decisionへの橋を1回だけ明確にする。
5. 一般AIサービスは平易さを高く、開発ツール/OSSは中程度、認証・セキュリティ・論文・数理は
   専門性を許容する。ただし、どの題材でも核心と次Actionへの橋は省略しない。
""".strip()


def _heading_aware_max_explanatory_run(article: str) -> int:
    """Count uninterrupted dense explanatory paragraphs while treating headings as breaks."""
    current = 0
    maximum = 0
    for block in re.split(r"\n\s*\n", str(article or "")):
        value = block.strip()
        if not value:
            continue
        if re.match(r"^#{1,6}\s+", value):
            current = 0
            value = re.sub(r"^#{1,6}\s+[^\n]*(?:\n|$)", "", value, count=1).strip()
            if not value:
                continue
        compact = re.sub(r"\s+", "", value)
        is_explain = len(compact) >= 90 and not _PULL_MARKERS_RE.search(value)
        if is_explain:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def _opening_has_strong_reader_bridge(article: str) -> bool:
    text = re.sub(r"^#{1,6}\s+.*$", "", str(article or ""), flags=re.MULTILINE)
    opening = re.sub(r"\s+", " ", text[:1100]).strip()
    return bool(_STRONG_OPENING_BRIDGE_RE.search(opening))


def _token_explained_anywhere(token: str, article: str) -> bool:
    value = str(article or "")
    escaped = re.escape(token)
    ascii_token = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    patterns = (
        rf"{ascii_token}\s*[（(][^）)\n]{{2,90}}[）)]",
        rf"[（(][^）)\n]{{2,90}}[）)]\s*{ascii_token}",
        rf"[^。！？\n]{{3,90}}[（(]{escaped}[）)]",
        rf"{ascii_token}(?:とは|は、|は)[^。！？\n]{{4,110}}(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール|方法|役割)",
    )
    return any(re.search(pattern, value, re.I) for pattern in patterns)


def _token_is_stable_compound_label(token: str, article: str) -> bool:
    """Ignore a two-letter token only when every occurrence belongs to one stable label."""
    if len(token) != 2 or not token.isupper():
        return False
    matches = list(re.finditer(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", str(article or "")))
    if not matches:
        return False
    followers: list[str] = []
    for match in matches:
        tail = str(article or "")[match.end():match.end() + 40]
        follower = re.match(r"\s+([A-Z][a-z][A-Za-z0-9.+-]{1,24})(?![A-Za-z0-9])", tail)
        if not follower:
            return False
        followers.append(follower.group(1))
    return len(set(followers)) == 1


def _token_is_non_jargon_compound(token: str, article: str) -> bool:
    """Ignore only proven ordinary labels from the Run38 artifact, never the bare token."""
    value = str(article or "")
    if token == "A4":
        matches = list(re.finditer(r"(?<![A-Za-z0-9])A4(?![A-Za-z0-9])", value))
        return bool(matches) and all(re.match(r"\s*(?:用紙|紙|サイズ)", value[m.end():m.end() + 12]) for m in matches)
    if token == "MIT":
        matches = list(re.finditer(r"(?<![A-Za-z0-9])MIT(?![A-Za-z0-9])", value, re.I))
        return bool(matches) and all(re.match(r"\s*(?:ライセンス|License)", value[m.end():m.end() + 18], re.I) for m in matches)
    return False


def _token_is_hardware_model_context(token: str, article: str) -> bool:
    """Do not mistake vendor/model labels such as NVIDIA RTX 4080 GPU for concepts.

    The exemption is contextual rather than a vendor allowlist: every occurrence must sit in
    a hardware model expression containing a model identifier and a hardware class. Bare
    acronyms still require explanation and remain reviewable.
    """
    value = str(article or "")
    escaped = re.escape(token)
    matches = list(re.finditer(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", value, re.I))
    if not matches:
        return False

    hardware_re = re.compile(
        rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        r"[^。！？\n]{0,48}\b[A-Z]{0,4}\d{2,5}[A-Za-z0-9-]*\b"
        r"[^。！？\n]{0,28}\b(?:GPU|CPU|TPU|NPU)\b",
        re.I,
    )
    return all(hardware_re.search(value, max(0, match.start() - 2), min(len(value), match.end() + 90))
               for match in matches)


def _correct_unexplained_jargon(base: dict[str, Any], article: str) -> list[str]:
    corrected: list[str] = []
    for raw in list(base.get("unexplained_jargon") or []):
        token = str(raw or "").strip()
        if not token or token == "PC":
            continue
        if _token_is_non_jargon_compound(token, article):
            continue
        if _token_is_hardware_model_context(token, article):
            continue
        if _token_explained_anywhere(token, article):
            continue
        if _token_is_stable_compound_label(token, article):
            continue
        corrected.append(token)
    return corrected[:8]


def _repeated_cross_paragraph_fragments(article: str) -> list[str]:
    """Reproduce the canonical 7-char repetition evidence without treating it as semantics."""
    prose = re.sub(r"^#{1,6}\s+.*$", "", str(article or ""), flags=re.MULTILINE)
    paragraphs = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    counts: dict[str, int] = {}
    for para in paragraphs:
        compact = re.sub(
            r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+|[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.\-]+",
            "",
            para,
        )
        seen: set[str] = set()
        for idx in range(max(0, len(compact) - 6)):
            piece = compact[idx:idx + 7]
            if len(piece) == 7:
                seen.add(piece)
        for piece in seen:
            counts[piece] = counts.get(piece, 0) + 1
    return sorted(piece for piece, count in counts.items() if count >= 3)


def _has_semantic_repetitive_insight(article: str) -> bool:
    """Require repeated predicate-bearing meaning, not only repeated topic nouns."""
    semantic = [
        piece for piece in _repeated_cross_paragraph_fragments(article)
        if _REPETITION_PREDICATE_RE.search(piece)
    ]
    return len(semantic) >= 2


def _topic_plainness_profile(article: str) -> str:
    """Return HIGH/MEDIUM/LOW plainness requirement without changing factual rigor."""
    value = str(article or "")
    if _SPECIALIST_TOPIC_RE.search(value):
        return "LOW"
    if _DEVELOPER_TOPIC_RE.search(value):
        return "MEDIUM"
    return "HIGH"


def _decision_accessibility(article: str, signals: dict[str, Any], corrected_jargon: list[str]) -> dict[str, Any]:
    """Measure whether a non-specialist can decide, independent of raw jargon density."""
    value = re.sub(r"```.*?```", "", str(article or ""), flags=re.S)
    opening = re.sub(r"\s+", " ", value[:1400])
    profile = _topic_plainness_profile(value)

    what = bool(re.search(r"(?:発表|公開|更新|変更|追加|登場|対応|提供|導入|実装|研究|提案|開発)", opening))
    why = bool(_DECISION_BRIDGE_RE.search(opening) or _DECISION_BRIDGE_RE.search(value))
    capability_limit = bool(_CAPABILITY_LIMIT_RE.search(value))
    action = bool(signals.get("explicit_reader_decision_action")) or bool(_ACTION_RE.search(value))
    opening_bridge = bool(_DECISION_BRIDGE_RE.search(opening)) or _opening_has_strong_reader_bridge(value)

    term_bridge = not corrected_jargon
    core = bool(what and why and capability_limit and action and opening_bridge and term_bridge)
    return {
        "profile": profile,
        "what_is_it": what,
        "why_it_matters": why,
        "capability_or_limit": capability_limit,
        "next_action": action,
        "opening_decision_bridge": opening_bridge,
        "required_term_bridge": term_bridge,
        "core": core,
    }


def correct_reader_signals(article: str, original: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic reader precision while preserving Decision Intelligence."""
    signals = dict(original or {})
    if not signals:
        return signals

    technical_density = float(signals.get("technical_terms_per_1000_chars") or 0.0)
    opening_density = float(signals.get("opening_technical_terms_per_1000_chars") or 0.0)
    plain_bridge = bool(signals.get("plain_language_bridge_present"))
    dense_paragraphs = int(signals.get("jargon_dense_paragraph_count") or 0)
    implementation_count = int(signals.get("implementation_identifier_count") or 0)
    analogy_hits = int(signals.get("analogy_hits") or 0)

    corrected_jargon = _correct_unexplained_jargon(signals, article)
    signals["unexplained_jargon"] = corrected_jargon
    bridge_needed = bool(corrected_jargon) or technical_density >= 26.0
    signals["bridge_needed"] = bridge_needed
    signals["analogy_necessary"] = (
        signals.get("analogy_necessary")
        if bool(signals.get("analogy_used"))
        else ("BRIDGE_RECOMMENDED" if bridge_needed and not plain_bridge else "NOT_REQUIRED")
    )

    if opening_density < 42.0 and (_opening_has_strong_reader_bridge(article) or not bridge_needed):
        signals["opening_non_engineer_access"] = "GOOD"

    heading_run = _heading_aware_max_explanatory_run(article)
    signals["max_explanatory_paragraph_run"] = heading_run
    signals["reader_temperature_rhythm"] = "GOOD" if heading_run <= 2 else "REVIEW"
    if heading_run <= 2:
        signals["narrative_pull"] = "GOOD"

    globally_readable_local_density = (
        technical_density < 30.0
        and not corrected_jargon
        and plain_bridge
        and implementation_count == 0
        and heading_run <= 2
        and signals.get("opening_non_engineer_access") == "GOOD"
        and dense_paragraphs <= 4
    )
    effective_dense_paragraphs = 1 if dense_paragraphs > 1 and globally_readable_local_density else dense_paragraphs
    signals["run351_effective_dense_paragraph_count"] = effective_dense_paragraphs

    decision_access = _decision_accessibility(article, signals, corrected_jargon)
    signals["plainness_requirement"] = decision_access["profile"]
    signals["decision_accessibility"] = "GOOD" if decision_access["core"] else "REVIEW"
    signals["decision_accessibility_dimensions"] = {
        key: value for key, value in decision_access.items() if key not in {"core", "profile"}
    }

    density_tolerated = bool(
        decision_access["core"] and decision_access["profile"] in {"MEDIUM", "LOW"}
    )

    jargon_translation = (
        "GOOD"
        if density_tolerated
        else ("GOOD" if not (bridge_needed and not plain_bridge) and effective_dense_paragraphs <= 1 else "REVIEW")
    )
    signals["jargon_translation"] = jargon_translation
    signals["non_engineer_core_clarity"] = (
        "GOOD"
        if decision_access["core"] or (jargon_translation == "GOOD" and (not bridge_needed or plain_bridge))
        else "REVIEW"
    )
    signals["plain_language_bridge"] = "GOOD" if plain_bridge or not bridge_needed else "REVIEW"

    issues = [
        str(item)
        for item in list(signals.get("accessibility_issues") or [])
        if str(item) not in {
            "unexplained_acronyms",
            "plain_language_bridge_missing",
            "jargon_translation_weak",
            "opening_non_engineer_access_weak",
            "reader_temperature_rhythm_weak",
        }
    ]
    if density_tolerated:
        issues = [item for item in issues if item != "technical_term_concentration"]
    if corrected_jargon:
        issues.append("unexplained_acronyms")
    if bridge_needed and not plain_bridge and not density_tolerated:
        issues.append("plain_language_bridge_missing")
    if jargon_translation != "GOOD":
        issues.append("jargon_translation_weak")
    if signals.get("opening_non_engineer_access") != "GOOD" and not decision_access["opening_decision_bridge"]:
        issues.append("opening_non_engineer_access_weak")
    if signals.get("reader_temperature_rhythm") != "GOOD":
        issues.append("reader_temperature_rhythm_weak")
    signals["accessibility_issues"] = list(dict.fromkeys(issues))
    signals["accessibility"] = "GOOD" if not signals["accessibility_issues"] else "REVIEW"

    semantic_repetition = _has_semantic_repetitive_insight(article)
    enjoyment = []
    for item in list(signals.get("enjoyment_issues") or []):
        value = str(item)
        if value == "explanation_run_long" and heading_run < 4:
            continue
        if value == "repetitive_insight" and not semantic_repetition:
            continue
        enjoyment.append(value)
    signals["enjoyment_issues"] = list(dict.fromkeys(enjoyment))
    signals["reader_enjoyment"] = "GOOD" if not signals["enjoyment_issues"] else "REVIEW"

    if signals.get("information_budget") == "REVIEW":
        no_known_budget_trigger = (
            effective_dense_paragraphs < 3
            and not (analogy_hits >= 3 and technical_density >= 30.0)
            and not (heading_run >= 4 and technical_density >= 26.0)
            and not (implementation_count >= 10 and effective_dense_paragraphs >= 2)
        )
        if no_known_budget_trigger:
            signals["information_budget"] = "GOOD"

    signals["run275_precision_overlay"] = True
    signals["run276_semantic_repetition_precision"] = True
    signals["run351_reader_density_precision"] = True
    signals["run397_decision_accessibility"] = True
    return signals


def _malformed_surface_issue(article: str) -> str:
    prose = re.sub(r"```.*?```|`[^`\n]+`", "", str(article or ""), flags=re.S)
    if _GA_NI_COLLISION_RE.search(prose):
        return READER_VALUE_MARKER + "final_surface_malformed_japanese_surface:particle_collision_ga_ni"
    return ""


def install(pipeline_module: Any) -> Any:
    """Install after historical reader/final-surface layers; zero API and idempotent."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original_signals = getattr(pipeline_module, "_reader_experience_signals", None)
    original_human_appeal = getattr(pipeline_module, "validate_human_appeal_gate", None)
    original_prompt = getattr(pipeline_module, "build_decision_prompt", None)
    original_retry_instruction = getattr(pipeline_module, "build_dynamic_retry_instruction", None)

    if callable(original_signals):
        def corrected_signals(article: str) -> dict[str, Any]:
            return correct_reader_signals(article, original_signals(article))
        pipeline_module._reader_experience_signals = corrected_signals

    if callable(original_human_appeal):
        def validate_with_surface_precision(parsed: dict, peer_articles=None):
            state, issues = original_human_appeal(parsed, peer_articles)
            merged = list(issues or [])
            issue = _malformed_surface_issue(str((parsed or {}).get("note_draft") or ""))
            if issue and issue not in merged:
                merged.append(issue)
                state = "WEAK"
            return state, merged
        pipeline_module.validate_human_appeal_gate = validate_with_surface_precision

    if callable(original_prompt):
        def build_decision_prompt_with_decision_accessibility(*args: Any, **kwargs: Any) -> str:
            prompt = str(original_prompt(*args, **kwargs) or "")
            if "Decision Accessibility Contract" in prompt:
                return prompt
            return prompt.rstrip() + "\n\n" + DECISION_ACCESSIBILITY_CONTRACT + "\n"
        pipeline_module.build_decision_prompt = build_decision_prompt_with_decision_accessibility

    if callable(original_retry_instruction):
        def build_retry_instruction_with_decision_accessibility(reason_rows: list[dict]):
            instruction, sections = original_retry_instruction(reason_rows)
            instruction = str(instruction or "")
            if "Decision Accessibility Contract" not in instruction:
                instruction = instruction.rstrip() + "\n\n" + DECISION_ACCESSIBILITY_CONTRACT
            return instruction, sections
        pipeline_module.build_dynamic_retry_instruction = build_retry_instruction_with_decision_accessibility

    pipeline_module.RUN397_DECISION_ACCESSIBILITY = True
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
