from pathlib import Path

path = Path("pipeline.py")
text = path.read_text(encoding="utf-8")

marker = '\n\ndef validate_fact_gate(parsed: dict, repo_name: str, source_context: str = "", source: str = "",\n'
if marker not in text:
    raise SystemExit("validate_fact_gate insertion marker not found")
if "def _find_causal_inference_overclaims(" in text:
    raise SystemExit("Run157 helper already present; refusing duplicate patch")

helper = r'''

# Run157: high-precision guard against turning observational/correlational evidence
# into causal or financial-outcome claims. This path is deterministic and adds zero
# provider/API calls. It intentionally favors precision: causal checks activate only
# when the source itself signals observational/associative evidence and does not expose
# a causal-identification design; caveated interpretation remains publishable.
_OBSERVATIONAL_EVIDENCE_PATTERNS = (
    r"\bobservational\b", r"\bfield evidence\b", r"\bfield study\b",
    r"\bcorrelat(?:ion|ed|es|ional)\b", r"\bassociat(?:ed|ion|ions)\b",
    r"\bconsistent with\b", r"\bsuggest(?:s|ed|ing)?\b",
    r"\bwe (?:observe|observed|find|found|document|documented)\b",
    r"観察研究", r"相関", r"関連", r"示唆",
)

_CAUSAL_IDENTIFICATION_PATTERNS = (
    r"\brandomi[sz]ed(?: controlled)? (?:trial|experiment|study)\b",
    r"\binstrumental variable\b", r"\bdifference[- ]in[- ]differences\b",
    r"\bregression discontinuity\b", r"\bnatural experiment\b",
    r"\bcausal identification strategy\b",
    r"ランダム化(?:比較)?試験", r"無作為(?:化)?(?:比較)?試験", r"自然実験", r"操作変数法", r"回帰不連続",
)

_CAUSAL_OVERCLAIM_PATTERNS = (
    r"(?:その)?理由(?:は|が).{0,80}にあります[。！？]?",
    r"原因(?:は|が).{0,80}(?:にあります|である|です)[。！？]?",
    r"[^。！？\n]{1,80}(?:が|によって)[^。！？\n]{0,80}(?:を引き起こす|をもたらす|につながる|を生み出す)[。！？]?",
    r"\b(?:causes?|caused|because of|due to|leads? to|results? in)\b",
)

_CAUSAL_CAVEAT_PATTERN = re.compile(
    r"可能性|示唆|と考えられ|と解釈|仮説|断定でき(?:ない|ません)|"
    r"因果(?:関係)?(?:は|を)?.{0,24}(?:不明|未検証|示せない|断定できない)|"
    r"相関|関連にとどま|may|might|could|suggest|consistent with|cannot infer|not establish caus",
    re.I,
)

_ROI_CLAIM_PATTERN = re.compile(r"\bROI\b|投資対効果|投資の成果|return on investment", re.I)
_ROI_MEASURED_EVIDENCE_PATTERN = re.compile(
    r"(?:measure|estimate|evaluate|calculate|report|observe|find|found).{0,100}"
    r"(?:\bROI\b|return on investment|financial return|revenue impact|profit(?:ability)?|cost savings?)|"
    r"(?:\bROI\b|return on investment|financial return|revenue impact|profit(?:ability)?|cost savings?).{0,100}"
    r"(?:measur|estimat|evaluat|calculat|report|observ|increase|decrease|improv|\d+%|\$)",
    re.I,
)
_ROI_NEGATION_PATTERN = re.compile(
    r"(?:does not|did not|not|cannot|can't|without).{0,40}(?:measure|estimate|evaluate|calculate|report)|"
    r"(?:measure|estimate|evaluate|calculate|report).{0,40}(?:not|no |without)|"
    r"測っていない|測定していない|推定していない|評価していない|検証していない|扱っていない",
    re.I,
)
_ROI_CAVEAT_PATTERN = re.compile(
    r"断定でき(?:ない|ません)|分からない|不明|測っていない|測定していない|"
    r"検証していない|示していない|扱っていない|cannot (?:infer|conclude|determine)|"
    r"not (?:measure|measured|estimate|estimated|evaluate|evaluated)",
    re.I,
)


def _source_has_measured_roi_evidence(source_context: str) -> bool:
    for sentence in re.split(r"(?<=[。！？.!?])\s+|\n+", source_context or ""):
        sent = sentence.strip()
        if not sent or _ROI_NEGATION_PATTERN.search(sent):
            continue
        if _ROI_MEASURED_EVIDENCE_PATTERN.search(sent):
            return True
    return False


def _find_causal_inference_overclaims(draft: str, source_context: str) -> list[str]:
    """Reject correlation→causation and unsupported ROI leaps with high precision."""
    article = draft or ""
    evidence = source_context or ""
    if not article or not evidence:
        return []

    failures: list[str] = []
    observational = any(re.search(pattern, evidence, re.I) for pattern in _OBSERVATIONAL_EVIDENCE_PATTERNS)
    causal_design = any(re.search(pattern, evidence, re.I) for pattern in _CAUSAL_IDENTIFICATION_PATTERNS)

    if observational and not causal_design:
        for sentence in re.split(r"(?<=[。！？.!?])\s+|\n+", article):
            sent = sentence.strip()
            if not sent or _CAUSAL_CAVEAT_PATTERN.search(sent):
                continue
            if any(re.search(pattern, sent, re.I) for pattern in _CAUSAL_OVERCLAIM_PATTERNS):
                failures.append("causal inference overclaim: observational evidence upgraded to causation")
                break

    if _ROI_CLAIM_PATTERN.search(article) and not _source_has_measured_roi_evidence(evidence):
        for sentence in re.split(r"(?<=[。！？.!?])\s+|\n+", article):
            if _ROI_CLAIM_PATTERN.search(sentence) and not _ROI_CAVEAT_PATTERN.search(sentence):
                failures.append("unsupported outcome extrapolation: ROI/financial outcome not measured by evidence")
                break

    return failures
'''

before_gate, gate_and_after = text.split(marker, 1)
text = before_gate + helper + marker + gate_and_after

call_anchor = "    failures.extend(_find_entity_relation_violations(draft, source_context))\n"
if call_anchor not in gate_and_after:
    raise SystemExit("fact gate call anchor not found")
gate_and_after = gate_and_after.replace(
    call_anchor,
    call_anchor + "    failures.extend(_find_causal_inference_overclaims(draft, source_context))\n",
    1,
)
text = before_gate + helper + marker + gate_and_after

path.write_text(text, encoding="utf-8")
print("Run157 patch applied")
