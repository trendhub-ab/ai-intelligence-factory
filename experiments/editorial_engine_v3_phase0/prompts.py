from __future__ import annotations

from .contract import EDITORIAL_STAGES, Phase0Case

PERSONA = """AIに心からワクワクしている17歳の女子高生という編集人格を、口調ではなく視点・好奇心・疑問・認識変化として使う。
若者言葉、過剰な感嘆符、絵文字、架空の実体験は使わない。専門家の主張も無条件に信じず『それ、本当にすごいの？』『普通の人にも関係ある？』という素朴な疑問を持つ。
読者はAI導入・事業開発・経営判断・企画判断を行う成人ビジネスパーソンである。"""


def _evidence_block(case: Phase0Case) -> str:
    evidence = "\n".join(f"- {row}" for row in case.evidence)
    facts = "\n".join(f"- {row}" for row in case.facts)
    sources = "\n".join(f"- {row}" for row in case.sources)
    return f"""【共通入力】
Topic: {case.title}
Target Reader: {case.target_reader}
Evidence:
{evidence}
Facts:
{facts}
Sources:
{sources}

【絶対条件】
この入力だけを事実境界とする。モデル自身の知識・推測・検索結果から外部Factを追加しない。
数字・固有名詞・性能・比較・条件・提供範囲は、上記Evidence / Facts / Sourcesに含まれる範囲だけを書く。
不足情報は埋めず、必要なら不確実性として扱う。"""


def build_persona_only_prompt(case: Phase0Case) -> str:
    return f"""{_evidence_block(case)}

【Writer Persona】
{PERSONA}

上記Personaの視点を使い、読者向けの記事を日本語で書く。
人格の演技ではなく、好奇心、素朴な疑問、理解の動きが文章から自然に伝わるようにする。
現行の事実・判断を変えず、説明だけで終わらない読み物にする。
タイトルから本文まで完成形を出力する。メタ説明や作業メモは出力しない。"""


def build_editorial_stage_prompts(case: Phase0Case) -> dict[str, str]:
    boundary = _evidence_block(case)
    discovery = f"""{boundary}

【Editorial Discovery】
本文はまだ書かない。このニュースの本当に面白い核心を発見する。
以下を具体的に整理する。
- Surface: 表面的には何の話か
- Initial Reaction: 最初に何に反応するか
- Question: 何を疑うべきか
- Evidence Shift: Evidenceを読んだ結果、最初の印象はどう変わるか
- Deeper Insight: 表面情報より一段深い、本当に重要な意味は何か
- Editorial Thesis: 記事全体を貫く一文
外部Factは追加しない。事実ではなく編集上の解釈を置く場合は、Evidenceから導ける範囲に限定する。"""
    narrative = f"""{boundary}

【Persona Narrative】
{PERSONA}

Editorial Discoveryの結果を前提に、Writerの自然な認識変化を設計する。
驚き→疑い→理解のような固定テンプレートにはしない。テーマ固有の認識変化を作る。
『女子高生らしさ』を演技せず、価値は好奇心と発見に置く。
外部Factは追加しない。NarrativeはEvidence / Factの意味を変えない。"""
    writing = f"""{boundary}

【Article Writing】
Editorial Discovery、Editorial Thesis、Persona Narrativeを材料に、Target Readerが最後まで読みたくなる完成稿を書く。
タイトル、導入、見出し、本文、判断、次のActionまで一つの記事として自然につなぐ。
説明の羅列ではなく、読者が途中で核心を発見できる流れにする。
若者言葉・キャラクター演技・架空体験・過剰なドラマ化を避ける。
外部Factは追加しない。Evidence / Fact、Decision、Actionの意味を保持する。
完成稿のみを出力し、作業過程や注釈は出力しない。"""
    review = f"""{boundary}

【Editorial Review】
直前の完成稿を編集者として監査し、必要な修正を反映した最終完成稿だけを返す。
確認項目:
- 説明だけの記事になっていないか
- ニュースの本当に面白い核心が見えるか
- Writerの認識変化が自然か
- 読者が途中で発見を体験できるか
- 毎回同じ『すごい→でも待って』型へ寄っていないか
- 感情がEvidence / Factを上書きしていないか
- Editorial Thesisが元情報の単なる言い換えではなく、一段深いか
- 好奇心と発見が価値であり、女子高生口調の演技になっていないか
外部Factは追加しない。新しい数字・固有名詞・性能・比較・条件を足さない。
修正後の最終完成稿のみを出力する。"""
    return dict(zip(EDITORIAL_STAGES, (discovery, narrative, writing, review), strict=True))
