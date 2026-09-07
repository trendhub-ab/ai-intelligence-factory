"""Run226 — evidence-bounded Human Editorial Planning for free note articles.

Run274 consolidates the original planning contract after real Production showed that
correct but overlapping reader instructions can still push the model toward a dense
technical report. This layer remains prompt-only: no provider/API call and no gate
relaxation.
"""

from __future__ import annotations

from typing import Any


RUN226_MARKER = "RUN226_READER_DELIGHT_PLANNING"
_INSTALL_FLAG = "_run226_reader_delight_planning_installed"


def editorial_planning_contract() -> str:
    """Return the compact internal editorial plan used before article generation."""
    return f"""
[{RUN226_MARKER} — 無料note記事 / HUMAN EDITORIAL PLAN]
本文を書く前に、取得済みSOURCE BOUNDARY / Evidenceだけで次を内部決定する。これは思考用メモであり本文の固定見出しにしない。

1. Reader Tension — 非エンジニアが最初に知りたい疑問・自分との関係を1つ選ぶ。
2. Discovery — 読後に「そういうことだったのか」と残る記事固有の核心を1つ選ぶ。発表要約だけを核心にしない。
3. Concrete Consequence — その核心が読者の選択・使い方・導入判断に何を意味するかをEvidenceの範囲で示す。
4. Explanation Bridge — 核心を理解するのに本当に必要な専門概念だけを、普通の言葉から説明する。比喩・問い・scene・会話調は自然に理解を助ける場合だけ任意で使う。
5. Editorial Point of View — EvidenceとDecisionから編集者としてどこを重要と見るかを1本の視点として通す。

最終優先順位:
- Fact / Evidence / Decision / required qualifier / 重要な制約は絶対に落とさない。
- そのうえで、DiscoveryまたはDecisionを理解するために不要な周辺仕様・実装列挙・重複説明はARTICLEへ詰め込まない。
- 分かりやすさは新情報の足し算ではなく、選択・順序・削除・言い換えで作る。

安全境界:
- Evidenceにない数値baseline、時間、金額、日付、人物、会話、引用、利用実績、普及/トレンド、競合roadmap、因果関係を作らず、「多くの人は〜」等の多数派認識を創作しない。
- 一次情報の倍率や%を具体値へ換算するのはbaselineと換算後の値の双方がSOURCE BOUNDARYで直接確認できる場合だけ。暗算で分かりやすい例を捏造しない。
- 比喩はEvidenceではない。対応関係が弱い比喩や、比喩だけで技術的な芯を置き換える文章は禁止する。
- 「ですよね」「実は」「つまり」、問い、短文、箇条書き、比喩に回数ノルマを設けない。固定Hook分類を均等配分しない。5項目を本文の固定順序にしない。style countだけを新しいHard Gateにしない。
- 既存の出力schema、SOURCE BOUNDARY、Evidence-to-Decision、Decision Score、URL、Publication Contractを変更しない。

目標は、正確な技術レポートを親しみ語で飾ることではない。読者が疑問からDiscoveryへ進み、核心を理解できた快感と自分の判断を持って読み終える記事にする。
""".strip()


def augment_prompt(prompt: str) -> str:
    """Append the Run226 contract exactly once without altering the base prompt."""
    base = str(prompt or "")
    if RUN226_MARKER in base:
        return base
    return f"{base.rstrip()}\n\n{editorial_planning_contract()}\n"


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
