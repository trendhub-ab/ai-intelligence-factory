"""Run228 — evidence-preserving reader rhythm planning for free note articles.

Run274 shortens this contract after real Production proved that more editorial prose is
not automatically better. Run275 makes the subtractive rule explicit enough for weak-model
fallback: after two dense explanation paragraphs, advance to meaning/constraint/decision
instead of stacking a third technical block. The contract remains prompt-only and preserves
verified decision evidence.
"""
from __future__ import annotations

from typing import Any

RUN228_MARKER = "RUN228_READER_RHYTHM_PLANNING"
_INSTALL_FLAG = "_run228_reader_rhythm_planning_installed"


def reader_rhythm_contract() -> str:
    return f"""
[{RUN228_MARKER} — 無料note記事 / READER RHYTHM]
ARTICLEはEvidenceの保管庫ではない。Run226で選んだ1本のDiscoveryとDecisionへ、読者の理解が「理解→意味→判断」と前進するよう編集する。

優先順位:
- Evidence上重要な数値・条件・反証・制約は削らない。
- ただし、Discovery・重要制約・Decisionのどれにも影響しない実装詳細、周辺仕様、同じ核心の言い換えは削るか1文へ圧縮する。
- 技術Factを2つ以上続ける前に、それらが読者の理解や判断に本当に必要かを確認する。不要なら次のFactを足さない。
- 同じ節で長い技術説明が2段落続いたら、3段落目の技術説明を足す前に「それが読者に何を意味するか」「どんな制約が残るか」「何を判断するか」のどれかへ進む。見出しで論点が変わる場合は新しい節として扱う。
- 正式名称・略語・実装名・フラグ名は、それ自体がDiscovery・制約・Decisionに必要でなければ本文に出さない。必要なら最初の1回だけ普通の言葉で役割を添え、名称紹介を連続させない。
- 専門語は普通の言葉で役割を先に伝え、正式名称は必要になった時だけ出す。別の未説明専門語で説明しない。
- 各主要セクションは単なる「次の情報」で終わらず、Discovery・意味・制約・Decisionのどれかへ前進させる。
- dense_report_clusterやrepetitive_insightを避けるため、親しみ文を追加するのではなく、重複・汎用前置き・判断に不要な列挙を先に引く。
- non_engineer_access_failureを避けるため、核心理解に不要な専門語を残さず、必要な専門語はその場で一度だけ平易化する。

安全境界:
- Reader Rhythmのために新しいFact、数字、人物、会話、利用実績、因果、競合情報を作ることは禁止。
- Evidence条件・留保を省いて軽く見せない。安全性・重大リスクのテーマを無理に娯楽化しない。
- scene、比喩、問い、短文、会話調は理解を助ける時だけ使い、回数ノルマを設けない。
- 全記事を同じ問題提起→比喩→列挙→私なら、のテンプレートへ揃えない。

完成時は、新しい説明を足す前に削れるものを探す。「報告書の塊」が残っているなら、Evidenceを落とすのではなく周辺列挙と重複を減らし、記事固有のDiscoveryとDecisionが前に見える状態で終える。
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
