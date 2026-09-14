"""Run226 — evidence-bounded Editorial Blueprint for free note articles.

The layer began as Human Editorial Planning and remains prompt-only: no provider/API call,
no output-schema change, and no gate relaxation.  The current contract makes the planning
step explicit enough to prevent a technically correct manuscript from drifting into the
wrong editorial emphasis.  Existing five editorial lenses remain compatible, but they now
sit inside a concrete Blueprint that fixes the reader question, central conclusion, evidence
boundary, terminology budget, and decision before the Writer drafts prose.
"""

from __future__ import annotations

from typing import Any

from editorial_quality_memory import QUALITY_MEMORY_MARKER, quality_memory_contract


RUN226_MARKER = "RUN226_READER_DELIGHT_PLANNING"
EDITORIAL_BLUEPRINT_MARKER = "AIIF_EDITORIAL_BLUEPRINT_V1"
_INSTALL_FLAG = "_run226_reader_delight_planning_installed"


def editorial_planning_contract() -> str:
    """Return the internal Editorial Blueprint used before article generation."""
    return f"""
[{RUN226_MARKER} — 無料note記事 / {EDITORIAL_BLUEPRINT_MARKER}]
本文を書く前に、取得済みSOURCE BOUNDARY / Evidence / 既存DecisionだけでEDITORIAL BLUEPRINTを内部決定する。これは思考用メモであり、本文の固定見出し・出力schema・新しい事実源ではない。

EDITORIAL BLUEPRINT:
A. Target Reader — 今回の記事で最優先する読者像を1つに絞る。原則は非エンジニアでも核心と判断を追える読者設計とし、専門家だけに通じる前提知識を暗黙に要求しない。
B. Reader Question — 読者がこの記事で本当に答えを得たい疑問・困りごと・迷い・選択を1つに固定する。
C. Why Now — なぜ今この話を読む価値があるかを、取得済みEvidenceの範囲だけで1文にする。新規性・緊急性・普及をEvidenceなしで演出しない。
D. Central Conclusion — 記事全体で最も重要な結論を1文に固定する。発表要約ではなく、既存Decisionと整合した読者向けの中心判断にする。
E. Evidence Anchor — Central Conclusionを支える必要最小限のEvidenceを選ぶ。周辺仕様を網羅するためにEvidenceを増やさない。
F. Capability Boundary — 「できる」「できない」「まだ分からない」を分離する。「できない」は禁止・非対応・制約がSOURCE BOUNDARYで明示される場合だけ使い、単にEvidenceがない場合は「未確認/まだ分からない」とする。
G. Terminology Budget — Discovery / 制約 / Decisionの理解に必要な専門語だけを残す。正式名称・略語・実装名は最初の1回で役割を平易に示し、不要な名称紹介は削る。
H. Reader Decision — 既存Decisionを、読者が次に何をするか分かる具体的な言葉へ翻訳する。新しいDecisionを作らず、試す/待つ/見送る等の表現は既存DecisionとEvidenceに従う。

既存の5 editorial lensesは、上のBlueprintを文章へ落とすために使う:
1. Reader Tension — Reader Questionを冒頭の読者文脈へ変換する。冒頭は「読者の困りごと・迷い・選択」→普通の言葉で何が変わるか→必要な場合だけ正式な技術名、の順で入る。最初の段落を製品名・略語・実装名の説明から始めない。
2. Discovery — 読後に「そういうことだったのか」と残る記事固有の核心を1つ選ぶ。発表要約だけを核心にしない。
3. Concrete Consequence — その核心が読者の選択・使い方・導入判断に何を意味するかをEvidenceの範囲で示す。
4. Explanation Bridge — 核心を理解するのに本当に必要な専門概念だけを、普通の言葉から説明する。正式名称・略語・実装名は、それ自体がDiscovery・制約・Decisionに必要な時だけ出し、最初の1回で役割を平易に示す。比喩・問い・scene・会話調は自然に理解を助ける場合だけ任意で使う。
5. Editorial Point of View — EvidenceとDecisionから編集者としてどこを重要と見るかを1本の視点として通す。Central Conclusionと矛盾する別の主張を後段で増やさない。

最終優先順位:
- Fact / Evidence / Decision / required qualifier / 重要な制約は絶対に落とさない。
- そのうえで、DiscoveryまたはDecisionを理解するために不要な周辺仕様・実装列挙・重複説明・名称紹介はARTICLEへ詰め込まない。
- 分かりやすさは新情報の足し算ではなく、選択・順序・削除・言い換えで作る。
- Blueprintは新しいHard Gateではない。Writerを正しい編集方向へ固定し、後段Gate同士の修復競合を減らすための生成前契約である。

安全境界:
- Evidenceにない数値baseline、時間、金額、日付、人物、会話、引用、利用実績、普及/トレンド、競合roadmap、因果関係を作らず、「多くの人は〜」等の多数派認識を創作しない。
- 一次情報の倍率や%を具体値へ換算するのはbaselineと換算後の値の双方がSOURCE BOUNDARYで直接確認できる場合だけ。暗算で分かりやすい例を捏造しない。
- 比喩はEvidenceではない。対応関係が弱い比喩や、比喩だけで技術的な芯を置き換える文章は禁止する。
- 「ですよね」「実は」「つまり」、問い、短文、箇条書き、比喩に回数ノルマを設けない。固定Hook分類を均等配分しない。5項目やBlueprint 8項目を本文の固定順序にしない。style countだけを新しいHard Gateにしない。
- 既存の出力schema、SOURCE BOUNDARY、Evidence-to-Decision、Decision Score、URL、Publication Contractを変更しない。

目標は、正確な技術レポートを親しみ語で飾ることではない。読者が自分の疑問からDiscoveryへ進み、核心を理解できた快感と自分の判断を持って読み終える記事にする。
""".strip()


def augment_prompt(prompt: str) -> str:
    """Append Blueprint and quality memory exactly once without altering base prompt."""
    base = str(prompt or "")
    additions: list[str] = []
    if RUN226_MARKER not in base:
        additions.append(editorial_planning_contract())
    if QUALITY_MEMORY_MARKER not in base:
        additions.append(quality_memory_contract())
    if not additions:
        return base
    return f"{base.rstrip()}\n\n" + "\n\n".join(additions) + "\n"


def install(pipeline_module: Any) -> None:
    """Install Run226 on a pipeline-like module, idempotently."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return

    original = pipeline_module.build_decision_prompt

    def wrapped_build_decision_prompt(*args: Any, **kwargs: Any) -> str:
        return augment_prompt(original(*args, **kwargs))

    pipeline_module.build_decision_prompt = wrapped_build_decision_prompt
    setattr(pipeline_module, _INSTALL_FLAG, True)
    setattr(pipeline_module, RUN226_MARKER, True)
    setattr(pipeline_module, EDITORIAL_BLUEPRINT_MARKER, True)
