#!/usr/bin/env python3
"""Surgically reconcile Run131 Reader Proximity + Information Budget.

Fail-closed patch against the latest main-derived integration branch. It changes
only editorial prompt guidance, zero-API reader diagnostics, and Article Audit
visibility. Hard gates, retry budgets, Notion schema, and Gemini call sites are
left untouched.
"""
from pathlib import Path


PATH = Path("pipeline.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if '"reader_proximity_moment_count": reader_proximity_moments' in text:
        print("Run131 Reader Proximity already present; no change")
        return

    style_old = '''・語り口は「教師が講義する」より「AIやITに詳しい友人が隣で、面白いところを一緒に見せてくれる」距離感を狙う。です・ます調を土台にしつつ、難しい概念の翻訳、身近な場面への接続、意外性、読者が実体験を思い出す箇所では、自然な会話調を少量混ぜてよい。
・「ですよね。」「やっぱり、」「なんですよ。」「ちょっと想像してみてください。」「ここが面白いところです。」等は使用可能な例であり必須語ではない。1記事で同じ語尾・呼びかけを反復せず、記事ごとに語彙を変える。
'''
    style_new = '''・語り口は「教師が講義する」より「AIやITに詳しい友人が隣で、面白いところを一緒に見せてくれる」距離感にする。です・ます調を土台にし、1記事の中で原則1〜3箇所は、読者の実体験を思い出させる問いかけ、難しい名前への一言、身近な場面への接続など「読者との距離が近くなる一文」を自然に成立させる。Security / Risk等で軽い語りが不適切な場合は、無理な冗談ではなく静かな問いかけや平易な一言で距離を縮める。
・「ですよね。」「やっぱり、」「なんですよ。」「ちょっと想像してみてください。」「ここが面白いところです。」等は使用可能な例であり必須語ではない。固定語でもない。特定の語尾を義務化せず、役割としての親近感を満たす。1記事で同じ語尾・呼びかけを反復せず、記事ごとに語彙を変える。
・親しみやすさのために文章を足し算しない。会話的な一文や日常例は、既存の硬い説明・接続文を置き換えて作る。独立した雑談段落を追加せず、同じ事実を「専門説明＋比喩説明」で二重に説明しない。
・この記事で読者が持ち帰る専門概念を内部で2〜4個に絞る。Decisionを理解するために必須の概念だけを日常語や短い比喩で丁寧に翻訳し、それ以外の実装詳細・規格名・略語は、Evidenceと制約を失わない範囲で一文にまとめるか、本文理解に不要なら書かない。専門語の数を増やすことを専門性と取り違えない。
・文字数上限の中でAccessibilityを足すためにEvidence、数値、制約、比較、反証、Decisionを削らない。削る優先順位は、重複説明、Decisionに不要な内部実装、汎用的な前置き、同じ意味の言い換え。分かりやすさは情報量の水増しではなく、情報の選択と順序で作る。
'''
    text = replace_once(text, style_old, style_new, "Run131 editorial style rules")

    fact_anchor = '''・「ですよね。」は読者に同意を強要するためではなく、スマホの権限確認、買い物、通勤など多くの人が経験した具体場面を思い出してもらう用途に限る。根拠のない一般化や価値観への同意要求には使わない。
・Fact / Evidence / 数値 / 制約 / Security上の重要事項は会話調でぼかさず、冷静で断定範囲の明確な文体を保つ。説明は親しみやすく、Evidenceは冷静に、Decisionは頼れる温度にする。
'''
    fact_replacement = '''・「ですよね。」は読者に同意を強要するためではなく、スマホの権限確認、買い物、通勤など多くの人が経験した具体場面を思い出してもらう用途に限る。根拠のない一般化や価値観への同意要求には使わない。
・親近感の一文や比喩から、Evidenceにない固有名詞・数値・市場評価・利用実績を新しく作らない。比喩は理解補助であり新しいFactではない。これにより親しみやすさを理由にFact Gate / Source Boundaryの表面積を増やさない。
・Fact / Evidence / 数値 / 制約 / Security上の重要事項は会話調でぼかさず、冷静で断定範囲の明確な文体を保つ。説明は親しみやすく、Evidenceは冷静に、Decisionは頼れる温度にする。
'''
    text = replace_once(text, fact_anchor, fact_replacement, "Run131 source-boundary rule")

    warmth_old = '''    conversational_patterns = [
        r"ですよね[。！？!?]", r"なんですよ[。！？!?]", r"やっぱり[、,]",
        r"ちょっと想像してみてください", r"ここが面白いところ",
        r"思い出してみてください", r"ありますよね[。！？!?]",
    ]
    conversational_hits = sum(len(re.findall(p, prose)) for p in conversational_patterns)
    repeated_conversational_phrase = any(len(re.findall(p, prose)) >= 3 for p in conversational_patterns)
    conversational_overuse = conversational_hits >= 7 or repeated_conversational_phrase
    conversational_warmth = bool(
        conversational_hits >= 1
        or scene_present
        or everyday_terms
        or re.search(r"(?:難しそう|身近|普段|私たち|使ったこと|見たこと|経験|思い浮かべ)", prose)
    )
'''
    warmth_new = '''    conversational_patterns = [
        r"ですよね[。！？!?]", r"なんですよ[。！？!?]", r"やっぱり[、,]",
        r"ちょっと想像してみてください", r"ここが面白いところ",
        r"思い出してみてください", r"ありますよね[。！？!?]",
        r"(?:使った|見た|聞かれた|困った|迷った)こと(?:は)?(?:ありませんか|ありますか|ありますよね)",
        r"(?:難しそう|大げさ|物々しい)(?:な名前|に見え|に聞こえ)[^。！？]{0,45}(?:ですが|けれど|ものの)",
        r"名前は難しそう[^。！？]{0,45}(?:ですが|でも)",
        r"(?:想像|思い浮かべ)して(?:みる|みて)",
    ]
    conversational_hits = sum(len(re.findall(p, prose)) for p in conversational_patterns)
    reader_question_hits = len(re.findall(r"(?:でしょうか|ませんか|ありますか|ありますよね|ですよね)[。！？!?]", prose))
    friendly_turn_hits = len(re.findall(r"(?:難しそう(?:ですが|でも)|名前は難し|意外と単純|やっていることは[^。！？]{0,35}(?:単純|シンプル)|身近な話にすると)", prose))
    reader_proximity_moments = conversational_hits + reader_question_hits + friendly_turn_hits
    repeated_conversational_phrase = any(len(re.findall(p, prose)) >= 3 for p in conversational_patterns)
    conversational_overuse = conversational_hits >= 7 or reader_question_hits >= 6 or repeated_conversational_phrase
    conversational_warmth = reader_proximity_moments >= 1
'''
    text = replace_once(text, warmth_old, warmth_new, "Run131 proximity signals")

    enjoyment_anchor = '''    if not news_relevance: enjoyment_issues.append("news_relevance_weak")
    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")

    accessibility = "GOOD" if not accessibility_issues else "REVIEW"
'''
    enjoyment_replacement = '''    if not news_relevance: enjoyment_issues.append("news_relevance_weak")
    if not conversational_warmth: enjoyment_issues.append("reader_proximity_missing")
    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")

    # Information-budget signal: do not solve accessibility by adding more prose. Several dense
    # jargon paragraphs plus many analogies indicate the article may be explaining everything twice.
    # This is diagnostic only; it never removes Evidence or changes a hard gate.
    information_budget = "GOOD"
    if jargon_dense_paragraphs >= 3 or (len(analogy_markers) >= 3 and technical_density >= 30.0):
        information_budget = "REVIEW"

    accessibility = "GOOD" if not accessibility_issues else "REVIEW"
'''
    text = replace_once(text, enjoyment_anchor, enjoyment_replacement, "Run131 soft diagnostics")

    return_anchor = '''        "conversational_warmth": "GOOD" if conversational_warmth and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "NEUTRAL"),
        "conversational_marker_count": conversational_hits,
        "conversational_overuse": conversational_overuse,
'''
    return_replacement = '''        "conversational_warmth": "GOOD" if conversational_warmth and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "conversational_marker_count": conversational_hits,
        "reader_proximity_moment_count": reader_proximity_moments,
        "reader_proximity": "GOOD" if reader_proximity_moments >= 1 and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),
        "information_budget": information_budget,
        "conversational_overuse": conversational_overuse,
'''
    text = replace_once(text, return_anchor, return_replacement, "Run131 return signals")

    audit_anchor = '''            f"- Conversational Warmth: {reader.get('conversational_warmth')}",
            f"- Conversational Marker Count: {reader.get('conversational_marker_count')}",
            f"- Headline Pull: {reader.get('headline_pull')}",
'''
    audit_replacement = '''            f"- Conversational Warmth: {reader.get('conversational_warmth')}",
            f"- Conversational Marker Count: {reader.get('conversational_marker_count')}",
            f"- Reader Proximity: {reader.get('reader_proximity')}",
            f"- Reader Proximity Moment Count: {reader.get('reader_proximity_moment_count')}",
            f"- Information Budget: {reader.get('information_budget')}",
            f"- Headline Pull: {reader.get('headline_pull')}",
'''
    text = replace_once(text, audit_anchor, audit_replacement, "Run131 audit output")

    PATH.write_text(text, encoding="utf-8")
    print("Run131 Reader Proximity + Information Budget reconciled successfully")


if __name__ == "__main__":
    main()
