"""Run226 — evidence-bounded Human Editorial Planning for free note articles.

This layer changes only the editorial planning instructions attached to the existing
article-generation prompt. It adds no model/API call site and does not weaken any
Fact / Evidence / Decision / Publication gate.
"""

from __future__ import annotations

from typing import Any


RUN226_MARKER = "RUN226_READER_DELIGHT_PLANNING"
_INSTALL_FLAG = "_run226_reader_delight_planning_installed"


def editorial_planning_contract() -> str:
    """Return the internal planning contract appended to the free-article prompt."""
    return f"""
[{RUN226_MARKER} — 無料note記事 / HUMAN EDITORIAL PLANNING]
本文を書き始める前に、取得済みSOURCE BOUNDARY / Evidenceだけを材料として、次の5点を内部で設計すること。これは思考用メモであり、5項目を見出しや定型欄として本文へ出力しない。

1. Reader Tension（読者の疑問・困りごと）
   この一次情報を初めて見る非エンジニアが、何を疑問に思うか／何が自分に関係するかをEvidenceから見つける。
2. Discovery（発見）
   読後に「そういうことだったのか」と腑に落ちる、記事固有の核心を1つ見つける。単なる発表要約を核心にしない。
3. Concrete Consequence（具体的な意味）
   Evidenceで確認できる範囲だけで、仕事・選択・使い方・導入判断の何が変わるのかを示す。読者向けに具体化するための架空の数字・期間・費用・人物・利用実績を作らない。
4. Explanation Bridge（理解の橋）
   専門知識がない読者が核心へ到達する説明順を決める。比喩・問い・scene・会話調は自然に理解を助ける場合だけ任意で使い、使わなくてもよい。
5. Editorial Point of View（編集者の視点）
   Evidenceと既存Decisionを踏まえ、この情報のどこを最も重要と見るかを記事全体へ自然に通す。末尾に義務的な「私なら」1文を貼るだけで済ませない。

安全境界:
- 人間らしさ・楽しさ・読みやすさは、SOURCE BOUNDARY、Fact、Evidence、Decision、数値条件、留保、反証より優先しない。
- Evidenceにない数値baseline、時間、金額、日付、人物、会話、引用、利用場面、導入実績、普及/トレンド、競合roadmap、因果関係、「多くの人は〜と思う」等の多数派認識を創作しない。
- 一次情報の「x倍」「%改善」等を、具体的な時間・金額・件数へ換算するのは、baselineと換算後の値の双方がSOURCE BOUNDARYで直接確認できる場合だけ。暗算で分かりやすい例を捏造しない。
- 比喩は技術理解の橋であってEvidenceではない。対応関係が弱い比喩、深刻なテーマを軽くする比喩、比喩だけで技術的な芯を置き換える文章は禁止。
- 「ですよね」「実は」「つまり」等の決まり文句、問いかけ、短文段落、箇条書き、比喩、Hook型について回数ノルマを設けない。自然さを数で作らない。
- 問題発見型／数値型／常識覆し型／実用型などの固定Hook分類を均等配分しない。入口・見出し順・段落順は、その記事固有のEvidenceとDiscoveryから決める。
- Reader Tension → Discovery → Concrete Consequence → Explanation Bridge → Editorial Point of View を本文の固定順序にしない。5点は構成を考えるための内部レンズであり、テンプレートではない。
- 既存のReader Experience / Human Appeal診断は維持し、段落文数・箇条書き数・問いの回数などのstyle countだけを新しいHard Gateにしない。
- 既存の出力schema、Evidence-to-Decision、Decision Score、URL、Sources、Publication Contractを一切変更しない。

目標:
正確な技術レポートを「親しみ語」で飾るのではなく、読者の疑問から発見へ進み、理解できた快感と自分の判断につながる記事にする。同じ書き手の記事を10本並べても、同じ導入・同じ比喩・同じ問い・同じ結論位置が反復しないこと。
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
