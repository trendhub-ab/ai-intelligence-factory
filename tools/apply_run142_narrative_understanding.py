from pathlib import Path

p = Path('pipeline.py')
s = p.read_text(encoding='utf-8')
original = s

# 1) Expand natural reader-question recognition so genuinely good prose is not rejected.
old = r'''reader_question_hits = len(re.findall(r"(?:でしょうか|ませんか|ありますか|ありますよね|ですよね)[。！？!?]", prose))'''
new = r'''reader_question_hits = len(re.findall(r"(?:でしょうか|ませんか|ありますか|ありますよね|ですよね|感じませんか|思いませんか|考えたくなりますよね)[。！？!?]", prose))'''
if old not in s:
    raise SystemExit('reader_question_hits anchor not found')
s = s.replace(old, new, 1)

# 2) Calculate Run142 diagnostics BEFORE the existing Run140 Reader Delight verdict.
anchor = '''    # Run140: composite reader outcome. This remains 0-API and soft-only: it does not trigger\n'''
if anchor not in s:
    raise SystemExit('Run140 anchor not found')
inject = r'''    # Run142: Narrative Understanding Progression.
    # Reader Delight must reflect understanding that moves forward, not a checklist of warm words.
    _paras = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    _body_after_opening = "\n\n".join(_paras[1:]) if len(_paras) > 1 else prose
    narrative_progression_hits = len(re.findall(
        r"(?:ところが|理由(?:の一つ)?が|なぜなら|その結果|だからこそ|だから|すると|そこで|一方で|でも|では導入すれば|つまり何が|何が困る|何を意味する|につながる|ためです|からです)",
        prose,
    ))
    causal_explanation_hits = len(re.findall(
        r"(?:理由|なぜ|ため|ので|その結果|だから|そこで|つまり|一方で|ところが|すると)", prose
    ))
    decision_or_implication_hits = len(re.findall(
        r"(?:私なら|判断|導入|安全性|意味|困る|価値|影響|使うなら|見るべき|確認|試して|比較)", prose
    ))
    factual_substance_hits = len(re.findall(
        r"(?:ニューロン|特徴|活性化|非直交|ベクトル|重み|回路|因果|制約|互換性|一次資料|Sparse Autoencoder|Superposition|Polysemanticity|辞書学習|スパース)",
        prose, re.I,
    ))
    analogy_hits = len(re.findall(
        r"(?:たとえば|例える|ような|みたい|押し入れ|収納|合鍵|家族|スマホ|料理|電車|棚|箱|引き出し)", prose
    ))
    report_style_body_hits = len(re.findall(
        r"(?:評価します|解析します|同定します|抽出します|確認します|検討します|必要があります|方式です|発生します|分布します)",
        _body_after_opening,
    ))
    body_reader_bridge_hits = len(re.findall(
        r"(?:ですよね|ませんか|感じませんか|思いませんか|難しそう|身近|困る|なぜ|だから|ところが|でも|そこで|私なら)",
        _body_after_opening,
    ))
    warm_hook_cold_body = (
        reader_proximity_moments >= 1
        and len(_paras) >= 3
        and report_style_body_hits >= 4
        and body_reader_bridge_hits <= 1
    )
    analogy_substance_thin = analogy_hits >= 3 and factual_substance_hits <= 3 and causal_explanation_hits <= 2
    practical_reader_progression = (
        len(_paras) >= 3
        and self_relevance
        and reader_proximity_moments >= 1
        and decision_or_implication_hits >= 3
        and factual_substance_hits >= 2
    )
    narrative_understanding_progression = (
        (
            narrative_progression_hits >= 2
            and causal_explanation_hits >= 2
            and decision_or_implication_hits >= 1
            and factual_substance_hits >= 2
        )
        or practical_reader_progression
    )
    if warm_hook_cold_body:
        enjoyment_issues.append("warm_hook_cold_body")
    if analogy_substance_thin:
        enjoyment_issues.append("analogy_substance_thin")
    if not narrative_understanding_progression:
        enjoyment_issues.append("narrative_understanding_progression_weak")

'''
s = s.replace(anchor, inject + anchor, 1)

# 3) Strengthen existing Run140 verdict. A strong meaning/decision arc can substitute for
# literal self-relevance tokens such as "仕事" or "生活"; this prevents false negatives on
# genuinely engaging science/AI explanations while adversarial warm-hook and analogy cases stay blocked.
old_verdict = '''    reader_delight = "GOOD" if reader_delight_good else "REVIEW"\n'''
new_verdict = '''    reader_delight_base = (\n        opening_non_engineer_access == "GOOD"\n        and reader_proximity_moments >= 1\n        and not conversational_overuse\n        and article_specific_angle\n        and (plain_language_bridge_present or not bridge_needed)\n        and (self_relevance or decision_or_implication_hits >= 2)\n    )\n    reader_delight = "GOOD" if (\n        reader_delight_base\n        and narrative_understanding_progression\n        and not warm_hook_cold_body\n        and not analogy_substance_thin\n    ) else "REVIEW"\n'''
if old_verdict not in s:
    raise SystemExit('reader_delight verdict anchor not found')
s = s.replace(old_verdict, new_verdict, 1)

# 4) Expose diagnostics.
needle = '        "reader_delight": reader_delight,\n'
if needle not in s:
    raise SystemExit('reader_delight return key not found')
s = s.replace(needle, needle + '''        "narrative_understanding_progression": "GOOD" if narrative_understanding_progression else "REVIEW",\n        "narrative_progression_hits": narrative_progression_hits,\n        "causal_explanation_hits": causal_explanation_hits,\n        "factual_substance_hits": factual_substance_hits,\n        "analogy_hits": analogy_hits,\n        "warm_hook_cold_body": warm_hook_cold_body,\n        "analogy_substance_thin": analogy_substance_thin,\n''', 1)

# 5) Audit fields.
needle2 = '            f"- Reader Delight: {reader.get(\'reader_delight\')}",\n'
if needle2 in s:
    s = s.replace(needle2, needle2 + '''            f"- Narrative Understanding Progression: {reader.get('narrative_understanding_progression')}",\n            f"- Warm Hook Cold Body: {reader.get('warm_hook_cold_body')}",\n            f"- Analogy Substance Thin: {reader.get('analogy_substance_thin')}",\n''', 1)

# 6) Prompt rules.
prompt_anchor = '・Reader Proximityは「使ってもよい装飾」ではなく、無料note記事の完成条件として扱う。'
if prompt_anchor not in s:
    raise SystemExit('prompt anchor not found')
addition = '''・Reader Delightは冒頭だけで作らない。導入で親近感を出した後に本文が技術レポートへ戻る構成は禁止する。記事全体で「読者の疑問 → 普通の言葉で理解 → なぜそうなるか → 何が面白い／困るか → 自分ならどう見る・判断するか」と理解が前へ進む流れを作る。各段落は前段落で生まれた疑問か意味を受け、情報カードの羅列にしない。\n・比喩は理解のための橋であり、面白さの代用品ではない。比喩だけで分かった気にさせず、比喩の直後または近接段落で「実際の技術では何が対応するのか」「なぜその現象が起きるのか」を最低1つ具体化する。かわいい例・日常例・口語表現が多くても、技術的な芯や因果が薄ければ完成としない。\n'''
s = s.replace(prompt_anchor, addition + prompt_anchor, 1)

if s == original:
    raise SystemExit('no changes')
p.write_text(s, encoding='utf-8')
print('Run142 patch applied')
