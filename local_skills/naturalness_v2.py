"""Targeted Local Skills guidance for an already-authorized quality retry."""
from __future__ import annotations

from editorial_naturalness_v2 import editorial_naturalness_v2_diagnostics


_GUIDANCE = {
    "section_structure_repetition": (
        "同じ『説明→意味→結論』の型を節ごとに繰り返さない。対象節の一部はEvidenceから始め、"
        "別の節は事実だけで止めるなど、情報を落とさず運びを変える。"
    ),
    "uniform_conclusion_cadence": (
        "各節を同じ強さの結論で閉じない。必要な強い判断だけ残し、重複するメタ要約や結論は"
        "文脈へ吸収する。"
    ),
    "speaker_voice_position_repetition": (
        "『私なら』等の話者判断を毎回同じ位置に置かない。Evidenceから判断が十分伝わる節では"
        "話者を前に出さず、具体的な条件・選択肢をそのまま置く。"
    ),
    "abstract_closing_cluster": (
        "抽象語だけの締めを重ねない。記事固有のEvidence・条件・Actionで閉じられる箇所は"
        "具体側へ戻す。"
    ),
}


def build_targeted_naturalness_repair_guidance(article_text: str) -> str:
    """Return local repair hints only for P1/P2 diagnostics.

    The helper never requests a retry and never changes Ready state.  It only adds
    precision to a quality retry that some other authoritative gate already allowed.
    """
    diagnostics = editorial_naturalness_v2_diagnostics(article_text)
    if not diagnostics.get("repair_required"):
        return ""

    rows = []
    for signal in diagnostics.get("signals") or []:
        if signal.get("severity") not in {"P1", "P2"}:
            continue
        code = str(signal.get("code") or "").strip()
        instruction = _GUIDANCE.get(code)
        if instruction:
            rows.append(f"・{code}: {instruction}")
    if not rows:
        return ""

    preservation = [
        "Fact / Evidence / Decisionの意味を変えない。",
        "数字・主体・時制・Source Boundary・required_qualifiersを保持する。",
        "情報量を減らさず、新しい事実・因果・体験を追加しない。",
        "問題が検出された文章の運びだけを局所的に再編集する。",
    ]
    return "\n".join(
        ["【Editorial Naturalness v2｜局所修正】", *rows, "【Preservation Contract】"]
        + [f"・{row}" for row in preservation]
    )
