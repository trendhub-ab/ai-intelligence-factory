"""Deterministic editorial quality memory for AIIF free-note generation.

This module is intentionally small and repository-owned.  It does not store user data,
Production manuscripts, provider responses, or mutable feedback.  It distills recurring
editorial lessons into prompt guidance that can be reviewed, tested, versioned, and included
in Publication Policy provenance.

The memory is guidance, not a new quality gate: Fact / Evidence / Decision / Publication
contracts remain authoritative.
"""
from __future__ import annotations


QUALITY_MEMORY_MARKER = "AIIF_EDITORIAL_QUALITY_MEMORY_V1"


def quality_memory_contract() -> str:
    """Return compact, evidence-safe editorial lessons for the Writer."""
    return f"""
[{QUALITY_MEMORY_MARKER} — EDITORIAL QUALITY MEMORY]
これは過去の編集上の成功/失敗から抽出した再利用ルールであり、Hard Gateや新しい事実源ではない。SOURCE BOUNDARY / Evidence / 既存Decisionと衝突する場合は、必ずそれらを優先する。

GOOD PATTERNS:
- 読者の疑問・迷いから入り、記事固有の中心結論を早めに示す。
- 技術名より先に「何が変わるか」「読者の判断にどう効くか」を普通の日本語で置く。
- 専門用語は核心・制約・Decisionに必要なものだけを、その場で短く説明する。
- 事実の列挙ではなく、Evidence → 意味 → 読者の判断、のつながりを1本通す。
- 具体例は理解を助け、かつSOURCE BOUNDARYで根拠を確認できる場合だけ使う。
- 複雑な題材でも、専門用語を消すのではなく、非専門読者が核心と判断を追える順序にする。

REJECT PATTERNS:
- 冒頭を製品名・略語・実装名の辞書説明から始める。
- 正しい情報を大量に並べるだけで、何が重要かの編集判断が見えない技術レポートにする。
- 同じ結論を言い換えて何度も繰り返し、記事を長くする。
- 「ですよね」「実は」「つまり」、問い、比喩、短文などを人間らしさのノルマとして機械的に挿入する。
- Evidenceにない一般論、多数派認識、利用実績、因果、具体数値を“分かりやすさ”のために補う。
- Evidenceが示していないことを「できない」と断定する。未確認は未確認のまま扱う。
- Gateを通すこと自体を目的化し、読者が読み終えたときの判断価値を失う。

編集上の優先順位は、Fact / Evidence / Decision / 重要な制約を守る → 中心結論を1つに絞る → 読者が核心と判断を追える順序へ編集する、の順とする。
""".strip()
