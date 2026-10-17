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

Article Writingの目的は無難な解説文に整えることではない。Editorial Discoveryで得た認識変化を、読者が本文の流れとして体験できる形で必ず運ぶ。
事実関係の修正に必要な場合を除き、以下の編集信号を削除しない。
- Initial Reaction: 読者が最初に反応する入口
- Question: そのテーマ固有の素朴な疑問
- Evidence Shift: Evidenceによって最初の見方が変わる転換
- Deeper Insight: 表面的な要約を越えた一段深い意味
- Persona Narrative: 好奇心・疑問・発見として現れる自然な認識変化
これらをラベルとして本文に列挙するのではなく、自然な文章の流れとして埋め込む。

若者言葉・キャラクター演技・架空体験・過剰なドラマ化を避ける。
外部Factは追加しない。Evidence / Fact、Decision、Actionの意味を保持する。
完成稿のみを出力し、作業過程や注釈は出力しない。"""
    review = f"""{boundary}

【Editorial Review】
直前の完成稿を編集者として監査し、必要な修正を反映した最終完成稿だけを返す。
Reviewの目的は文章を無難に整えることではない。Factを守りながら、Editorial DiscoveryとPersona Narrativeで得た『読者の認識が動く瞬間』を最終稿に保持すること。

以下は、事実関係の修正に必要な場合を除き、削除しない。
- Initial Reaction: 読者が最初に反応する入口
- Question: そのテーマ固有の素朴な疑問
- Evidence Shift: Evidenceによって最初の見方が変わる転換
- Deeper Insight: 表面的な要約を越えた一段深い意味
- Persona Narrative: 好奇心・疑問・発見として現れる自然な認識変化

確認項目:
- 説明だけの記事になっていないか
- ニュースの本当に面白い核心が見えるか
- Writerの認識変化が自然か
- 読者が途中で発見を体験できるか
- 毎回同じ『すごい→でも待って』型へ寄っていないか
- 感情がEvidence / Factを上書きしていないか
- Editorial Thesisが元情報の単なる言い換えではなく、一段深いか
- 好奇心と発見が価値であり、女子高生口調の演技になっていないか
- Persona Narrativeを無難な解説文へ戻していないか
- 文章を短く・整然とすること自体を優先し、Initial Reaction / Question / Evidence Shift / Deeper Insightを削っていないか
外部Factは追加しない。新しい数字・固有名詞・性能・比較・条件を足さない。
修正後の最終完成稿のみを出力する。"""
    return dict(zip(EDITORIAL_STAGES, (discovery, narrative, writing, review), strict=True))


def build_editorial_bundle_prompt(case: Phase0Case) -> str:
    """Run the four explicit editorial deliverables in one provider generation."""
    return f"""{_evidence_block(case)}

【Writer Persona】
{PERSONA}

以下の4つの編集成果物を、この順序で作成する。内部思考の説明は不要で、各工程の成果物だけを簡潔に出力する。

1. Editorial Discovery
- Surface: 表面的には何の話か
- Initial Reaction: 最初に何に反応するか
- Question: 何を疑うべきか
- Evidence Shift: Evidenceで最初の印象がどう変わるか
- Deeper Insight: 表面情報より一段深い意味
- Editorial Thesis: 記事全体を貫く一文
本文はまだ書かない。

2. Persona Narrative
Editorial Discoveryを受けて、Writerの自然な認識変化を設計する。
固定の『すごい→でも待って』型を避け、テーマ固有の好奇心・疑問・発見を作る。
女子高生口調の演技、若者言葉、架空体験は使わない。

3. Article Writing
DiscoveryとNarrativeを材料に、Target Readerが最後まで読みたくなる日本語の完成稿を書く。
タイトル、導入、見出し、本文、判断、次のActionまで自然につなぐ。
説明の羅列にせず、途中で核心を発見できる流れにする。
無難な解説文に整えることを目的にしない。事実関係の修正に必要な場合を除き、Initial Reaction / Question / Evidence Shift / Deeper Insight / Persona Narrativeを削除しない。
これらをラベルとして並べず、読者が『最初の見方→疑問→Evidenceによる転換→一段深い理解』を自然に体験できる文章として埋め込む。

4. Editorial Review
Article Writingを編集者として監査し、必要な修正を反映した最終完成稿を作る。
Reviewの目的は無難な解説文へ整えることではない。Factを守りながら、DiscoveryとPersona Narrativeで生まれた認識変化と温度を最終稿に保持する。
Evidence / Factを落とさず、外部Factを追加せず、AI臭・定型Narrative・過度な軽さを抑える。
Editorial Thesisが元情報の単なる言い換えでなく、一段深いか確認する。
事実関係の修正に必要な場合を除き、Initial Reaction / Question / Evidence Shift / Deeper Insight / Persona Narrativeを削除しない。
Persona Narrativeを無難な解説文へ戻さない。文章の短さ・整然さを、好奇心・疑問・発見より優先しない。

【出力形式】
Markdownフェンスや前置きは付けず、次の4キーだけを持つ有効なJSON objectで返す。
{{
  "Editorial Discovery": "編集成果物",
  "Persona Narrative": "編集成果物",
  "Article Writing": "初稿全文",
  "Editorial Review": "修正済み最終記事全文"
}}
4キーは必須・空欄禁止。外部Factは全工程で追加しない。"""
