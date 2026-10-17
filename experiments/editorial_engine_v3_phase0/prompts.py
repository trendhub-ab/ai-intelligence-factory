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
    reaction = f"""{boundary}

【Writer Reaction】
{PERSONA}

本文はまだ書かない。Evidenceに初めて触れたWriter自身の反応を、テーマ固有に整理する。
必須項目:
- Reaction: 最初に何へ反応したか
- Curiosity: 何をもっと知りたくなったか
- Question: 何がまだ分からず、何を確かめたいか
- Future Imagination: これが普通になった時に、どんな未来の変化をまず想像するか
- Emotion Intensity: LOW | MEDIUM | HIGH のいずれか。Evidenceの強さとテーマに合わせる

GenericなAI賛美は禁止。ReactionはEvidenceに反応して生まれるものであり、Evidenceの代わりではない。
外部Factは追加しない。"""
    discovery = f"""{boundary}

【Editorial Discovery】
Writer ReactionとEvidenceの緊張関係から、本文の核心を発見する。本文はまだ書かない。
必須項目:
- Surface: 表面的には何の話か
- Interesting Tension: Writerの最初の反応が、なぜそのままでは不十分か
- Evidence Pivot: どのEvidenceが見方を変える、または鋭くするか
- Deeper Insight: 見出しの一段下にある本当の意味
- Editorial Thesis: 記事全体を貫く一文

Dramaを捏造しない。Evidenceが最初の期待を確認する場合は『期待→さらに面白い』でもよい。
外部Factは追加しない。"""
    shift = f"""{boundary}

【Cognitive Shift】
{PERSONA}

Writer ReactionとEditorial Discoveryを受けて、Writerの理解がEvidenceによってどう動いたかを明示する。
必須項目:
- Before View: Evidenceを深く読む前の見方
- Evidence Encounter: 何に触れて理解が動いたか
- After View: Evidence後の見方
- What I Now Find Interesting: 今、いちばん面白いと感じる点

固定の感情曲線は禁止。confusion→understanding、skepticism→surprise、excitement→concern、small feature→large future implicationなど、テーマに合う変化を選ぶ。
同じ『すごい→でも待って』型を使い回さない。
外部Factは追加しない。"""
    article = f"""{boundary}

【Persona Article Generation】
{PERSONA}

Writer Reaction、Editorial Discovery、Cognitive Shiftを材料に、成人ビジネスパーソンが最後まで読みたくなる完成稿を書く。
タイトル、導入、見出し、本文、判断、次のActionまで自然につなぐ。

完成稿には、ラベルをそのまま見出し化せず、自然な文章として次のobservable signalを複数残す。
- Writer Reaction: Writer自身の反応
- Question: Writer自身の疑問
- Cognitive Shift: Evidenceによる見方の変化
- discovery: 本当に面白い点の発見
- Future Imagination または人への含意（Evidenceで支えられる場合）
- 発見からTarget Readerの判断への接続

一人称は自然なら使ってよい。『私たちは考えるべき』『疑問を抱くべき』のようなGeneric表現に隠さない。
若者言葉・キャラクター演技・架空体験・過剰なドラマ化を避ける。
外部Factは追加しない。Evidence / Fact、Decision、Actionの意味を保持する。
完成稿のみを出力する。"""
    review = f"""{boundary}

【Fact-Safe Review】
直前のPersona Article Generationを監査する。Default behaviorは、具体的な欠陥がない限り本文を変更しない。
欠陥がある場合だけ、最小の局所修正を行い、最終完成稿だけを返す。

確認対象:
- unsupported external Fact
- changed or invented numbers
- changed named entities
- Evidence contradiction
- decision/action distortion
- unsupported certainty
- Persona caricature or fabricated experience
- repeated narrative template
- obvious AI boilerplate that Writerの温度を潰さず除去できるか

禁止:
- 一人称を形式的理由だけで無人称へ変える
- 好奇心を主観だからという理由で削る
- specific question をGenericなビジネス表現へ置換する
- 全文を整然と見せるために再構成する
- Future Imagination が問い・含意としてEvidenceに支えられているのに削除する

外部Factは追加しない。必要修正がなければ、Persona Article Generationをそのまま返す。"""
    return dict(zip(EDITORIAL_STAGES, (reaction, discovery, shift, article, review), strict=True))


def build_editorial_bundle_prompt(case: Phase0Case) -> str:
    """Run all Reaction-First editorial deliverables in one provider generation."""
    return f"""{_evidence_block(case)}

【Writer Persona】
{PERSONA}

以下の5つの編集成果物を、この順序で作成する。内部思考の説明は不要で、各工程の成果物だけを返す。

1. Writer Reaction
- Reaction
- Curiosity
- Question
- Future Imagination
- Emotion Intensity: LOW | MEDIUM | HIGH
Evidence固有の反応にする。GenericなAI賛美は禁止。本文はまだ書かない。

2. Editorial Discovery
- Surface
- Interesting Tension
- Evidence Pivot
- Deeper Insight
- Editorial Thesis
Writer ReactionとEvidenceの間から、記事の本当の核心を発見する。Dramaは捏造しない。

3. Cognitive Shift
- Before View
- Evidence Encounter
- After View
- What I Now Find Interesting
固定の感情曲線を使わず、テーマ固有の認識変化にする。同じ『すごい→でも待って』型を使い回さない。

4. Persona Article Generation
Reaction / Question / Cognitive Shift / discovery を、成人ビジネス読者が自然に体験できる完成稿として書く。
一人称は自然なら使ってよい。若者言葉、キャラクター演技、架空体験は禁止。
Future Imagination または人への含意は、Evidenceで支えられる場合だけ残す。
発見をTarget Readerの判断と次のActionへ接続する。

5. Fact-Safe Review
Default behaviorは本文を変更しない。unsupported Fact、数字・固有名詞の変更、Evidence矛盾、decision/action歪曲、unsupported certainty、Persona caricature、fabricated experience、repeated template、明白なAI boilerplateのいずれかがある場合だけ、最小の局所修正をする。
一人称、好奇心、specific question、Evidenceに支えられたFuture Imaginationを、形式的な理由で削除しない。

【全工程共通】
外部Factを追加しない。数字・固有名詞・性能・比較・条件・提供範囲はEvidence / Facts / Sourcesの範囲だけを書く。

【出力形式】
Markdownフェンスや前置きは付けず、次の5キーだけを持つ有効なJSON objectで返す。5キーは必須・空欄禁止。
{{
  "Writer Reaction": "Reaction / Curiosity / Question / Future Imagination / Emotion Intensityを含む成果物",
  "Editorial Discovery": "Surface / Interesting Tension / Evidence Pivot / Deeper Insight / Editorial Thesisを含む成果物",
  "Cognitive Shift": "Before View / Evidence Encounter / After View / What I Now Find Interestingを含む成果物",
  "Persona Article Generation": "初稿全文",
  "Fact-Safe Review": "必要なら最小修正した最終記事全文。修正不要なら初稿をそのまま返す"
}}"""
