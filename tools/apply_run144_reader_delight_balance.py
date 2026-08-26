from pathlib import Path

p = Path('pipeline.py')
s = p.read_text(encoding='utf-8')
original = s

old_factual = '''    factual_substance_hits = len(re.findall(\n        r"(?:ニューロン|特徴|活性化|非直交|ベクトル|重み|回路|因果|制約|互換性|一次資料|Sparse Autoencoder|Superposition|Polysemanticity|辞書学習|スパース)",\n        prose, re.I,\n    ))\n'''
new_factual = '''    factual_substance_hits = len(re.findall(\n        r"(?:ニューロン|特徴|活性化|非直交|ベクトル|重み|回路|因果|制約|互換性|一次資料|"\n        r"Sparse Autoencoder|Superposition|Polysemanticity|辞書学習|スパース|"\n        r"権限|最小権限|アクセス|ログ|承認|監視|演算性能|メモリ|帯域|消費電力|ベンチマーク|"\n        r"コスト|冷却|モデル|トークン|暗号|認証|脆弱性|API|プロトコル)",\n        prose, re.I,\n    ))\n'''
if old_factual not in s:
    raise SystemExit('factual_substance anchor not found')
s = s.replace(old_factual, new_factual, 1)

old_progress = '''    practical_reader_progression = (\n        len(_paras) >= 3\n        and self_relevance\n        and reader_proximity_moments >= 1\n        and decision_or_implication_hits >= 3\n        and factual_substance_hits >= 2\n    )\n    narrative_understanding_progression = (\n        (\n            narrative_progression_hits >= 2\n            and causal_explanation_hits >= 2\n            and decision_or_implication_hits >= 1\n            and factual_substance_hits >= 2\n        )\n        or practical_reader_progression\n    )\n'''
new_progress = '''    # Run144: allow concise, genuinely useful prose to progress without mandatory catchphrases.\n    # A practical article may establish understanding through concrete technical substance, a caveat,\n    # and a reader-facing decision even when it does not use explicit connectors such as 「だから」 twice.\n    practical_reader_progression = (\n        len(_paras) >= 3\n        and decision_or_implication_hits >= 2\n        and factual_substance_hits >= 2\n        and opening_non_engineer_access == "GOOD"\n        and (self_relevance or plain_language_bridge_present or reader_proximity_moments >= 1)\n    )\n    narrative_understanding_progression = (\n        (\n            narrative_progression_hits >= 2\n            and causal_explanation_hits >= 2\n            and decision_or_implication_hits >= 1\n            and factual_substance_hits >= 2\n        )\n        or practical_reader_progression\n    )\n'''
if old_progress not in s:
    raise SystemExit('progress anchor not found')
s = s.replace(old_progress, new_progress, 1)

old_base = '''    reader_delight_base = (\n        opening_non_engineer_access == "GOOD"\n        and reader_proximity_moments >= 1\n        and not conversational_overuse\n        and article_specific_angle\n        and (plain_language_bridge_present or not bridge_needed)\n        and (self_relevance or decision_or_implication_hits >= 2)\n    )\n    reader_delight = "GOOD" if (\n        reader_delight_base\n        and narrative_understanding_progression\n        and not warm_hook_cold_body\n        and not analogy_substance_thin\n    ) else "REVIEW"\n'''
new_base = '''    # Run144: Reader Delight is a balance, not an AND-list of conversational tokens.\n    # Hard-negative patterns remain strict; positive quality can be demonstrated by multiple independent\n    # reader-value signals. This reduces false positives against calm Security/Hardware/Research prose.\n    reader_delight_overclaim = bool(re.search(\n        r"(?:完全に理解できれば|完全に整理できます|完全に取り出せ|ブラックボックス問題は解決|"\n        r"危険な挙動も事前に見抜け|必須条件にします|すぐ全社導入|私なら今のうちに導入します)",\n        prose, re.I,\n    ))\n    _insight_sentences = [x.strip() for x in sentences if len(re.sub(r"\\s+", "", x)) >= 22]\n    _near_repeat_pairs = 0\n    for _i, _left in enumerate(_insight_sentences):\n        _a = _sentence_shingles(_left)\n        if len(_a) < 5:\n            continue\n        for _right in _insight_sentences[_i + 1:_i + 5]:\n            _b = _sentence_shingles(_right)\n            if len(_b) >= 5 and _jaccard(_a, _b) >= 0.52:\n                _near_repeat_pairs += 1\n                break\n    repetitive_insight = _near_repeat_pairs >= 2\n    if reader_delight_overclaim:\n        enjoyment_issues.append("reader_delight_overclaim")\n    if repetitive_insight:\n        enjoyment_issues.append("repetitive_insight")\n\n    positive_reader_signals = sum(bool(x) for x in (\n        opening_non_engineer_access == "GOOD",\n        article_specific_angle,\n        plain_language_bridge_present or not bridge_needed,\n        self_relevance or reader_proximity_moments >= 1 or everyday_terms or scene_present,\n        factual_substance_hits >= 2,\n        decision_or_implication_hits >= 2,\n        narrative_understanding_progression,\n        curiosity or return_pull,\n    ))\n    reader_delight_base = (\n        positive_reader_signals >= 6\n        and opening_non_engineer_access == "GOOD"\n        and article_specific_angle\n        and (plain_language_bridge_present or not bridge_needed)\n        and factual_substance_hits >= 2\n        and decision_or_implication_hits >= 1\n    )\n    reader_delight = "GOOD" if (\n        reader_delight_base\n        and narrative_understanding_progression\n        and not conversational_overuse\n        and not warm_hook_cold_body\n        and not analogy_substance_thin\n        and not reader_delight_overclaim\n        and not repetitive_insight\n    ) else "REVIEW"\n'''
if old_base not in s:
    raise SystemExit('reader delight base anchor not found')
s = s.replace(old_base, new_base, 1)

needle = '        "reader_delight": reader_delight,\n'
if needle not in s:
    raise SystemExit('return anchor not found')
s = s.replace(needle, needle + '''        "reader_delight_positive_signals": positive_reader_signals,\n        "reader_delight_overclaim": reader_delight_overclaim,\n        "repetitive_insight": repetitive_insight,\n''', 1)

prompt_anchor = '・Reader Delightは冒頭だけで作らない。導入で親近感を出した後に本文が技術レポートへ戻る構成は禁止する。'
if prompt_anchor in s and '親近感は疑問形や相づちの数で採点しない' not in s:
    s = s.replace(prompt_anchor, '・親近感は疑問形や相づちの数で採点しない。Security・Risk・Hardware・Researchのようなテーマでは、落ち着いた語りでも、読者が普通の言葉で核心を理解し、制約と判断まで自然に到達できれば十分に人間的で親しみやすい。口語句を足すためだけの修正は禁止する。\n' + prompt_anchor, 1)

if s == original:
    raise SystemExit('no changes')
p.write_text(s, encoding='utf-8')
print('Run144 patch applied')
