"""Run228 — evidence-preserving reader rhythm planning for free note articles.

Run226 improved the editorial angle, but the first FULL Production run still produced several
manuscripts with a dense-report cluster: correct facts were stacked faster than the article
converted them into understanding, consequence, and decision. This layer changes only the
existing generation prompt. It adds no model/API call and no new style-count gate.
"""
from __future__ import annotations

from typing import Any

RUN228_MARKER = "RUN228_READER_RHYTHM_PLANNING"
_INSTALL_FLAG = "_run228_reader_rhythm_planning_installed"


def reader_rhythm_contract() -> str:
    return f"""
[{RUN228_MARKER} — 無料note記事 / READER RHYTHM & INFORMATION BUDGET]
Run226で決めたReader Tension / Discovery / Consequence / Explanation Bridge / Editorial Point of Viewを、本文の読み進めやすさまで一貫させる。事実を減らすのではなく、Evidenceを「理解→意味→判断」へ変換する呼吸を作ること。

編集原則:
- 技術Fact・ベンチマーク・実装詳細を連続して並べるだけの「報告書の塊」にしない。必要な技術説明を置いたら、その内容が何を意味するのか、読者の理解や選択がどう変わるのかへ自然に進んでから次の詳細へ移る。
- 記事には1本の主要な説明軸を通す。副次的な仕組み・列挙・周辺仕様は、核心理解、重要な制約、Decisionのどれにも影響しないなら無理に本文へ詰め込まない。
- Evidence上重要な数値・条件・反証・制約は削らない。情報量を軽く見せるためにEvidenceを落とすのではなく、重複説明、汎用前置き、Decisionに不要な実装列挙を減らす。
- 専門用語は、その語を知らない読者が直後の文を理解できる粒度で、その場で普通の言葉へ橋渡しする。辞書のような定義列挙にしない。
- 段落間では「次の事実」だけへ飛ばず、必要に応じて「だから何が面白いのか／困るのか／判断にどう効くのか」へ進める。ただし、この問いの文言自体を固定フレーズとして本文へ出力しない。
- 表や箇条書きの方が比較を正確かつ短く理解できる場合は使ってよい。逆に、読み物らしさを演出するためだけに表を散文へ崩さない。
- scene、比喩、問い、短文、会話調、感情語を「温度を上げる装飾」として追加しない。Evidence理解を助けるときだけ使う。
- 文長、段落文数、問い、比喩、箇条書き、見出し数に回数ノルマを設けない。記事ごとのEvidence密度とテーマの重さに合わせて自然に変える。
- セキュリティ、障害、重大リスクなど軽さが不適切なテーマでは、無理に面白くせず、明快さ・発見・判断可能性をReader Delightとみなす。

禁止:
- Reader Rhythmのために新しいFact、数字、人物、会話、利用実績、因果、競合情報を作ること。
- Evidenceの条件・留保を省いて文章だけを軽くすること。
- 「つまり」「ここで重要なのは」「実は」「ですよね」等の接続句を機械的に反復すること。
- 全記事を同じ「問題提起→比喩→3点列挙→私なら」の順序へ揃えること。

完成時セルフチェック:
記事を読み直し、各主要セクションが単なる情報追加で止まらず、記事固有のDiscoveryまたはDecisionへ前進しているかを見る。前進していない箇所は、新事実を足さず、重複・周辺列挙を整理し、既存Evidenceの意味が読者へ伝わる形へ整える。
""".strip()


def augment_prompt(prompt: str) -> str:
    base = str(prompt or "")
    if RUN228_MARKER in base:
        return base
    return f"{base.rstrip()}\n\n{reader_rhythm_contract()}\n"


def install(pipeline_module: Any) -> None:
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return

    original = pipeline_module.build_decision_prompt

    def wrapped_build_decision_prompt(*args: Any, **kwargs: Any) -> str:
        return augment_prompt(original(*args, **kwargs))

    pipeline_module.build_decision_prompt = wrapped_build_decision_prompt
    setattr(pipeline_module, _INSTALL_FLAG, True)
    setattr(pipeline_module, RUN228_MARKER, True)
