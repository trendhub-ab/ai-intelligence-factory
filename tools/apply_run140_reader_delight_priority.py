from pathlib import Path

path = Path('pipeline.py')
text = path.read_text(encoding='utf-8')

anchor = '・見出しは説明ラベルではなく、本文固有の意味と次を読む理由を持たせる。「なぜ重要か」「何が変わるか」「今後どうなるか」「最終判断」等を複数並べない。'
priority = '・【無料note記事の最上位編集目標】読み手が「楽しい」「わかりやすい」「自分にも関係がある」と感じ、AIやITに詳しい人から面白い話を聞いていたら、いつの間にか核心を理解できていた状態を最優先する。技術レポートとして整っているだけでは完成としない。Evidence・数値・制約・反証・Decisionの正確さは絶対に落とさず、それらを読者が自然に理解できる順番と言葉へ編集する。親近感は口語句の数ではなく、読者の経験・疑問・判断と本文がつながっていることで成立させる。\n'
if priority.strip() not in text:
    if anchor not in text:
        raise SystemExit('Run140 anchor missing: editorial priority')
    text = text.replace(anchor, priority + anchor, 1)

old_doc = '''    """Run127: 0-API soft diagnostics for reader pull without creating new hard gates.\n\n    The diagnostics distinguish accessibility from narrative/editorial pull. Missing analogy,\n    humor, everyday examples, or emotional language is never itself a failure.\n    """'''
new_doc = '''    """0-API diagnostics for reader pull without creating new hard gates.\n\n    Run140 treats delight as the combination of clarity, human proximity, and an article-specific\n    reason to keep reading. Missing analogy, humor, or a particular catchphrase is never itself\n    a failure; a plain but engaging explanation can still be GOOD.\n    """'''
if old_doc in text:
    text = text.replace(old_doc, new_doc, 1)

issue_anchor = '    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")\n\n    # Reader-value budget:'
issue_repl = '''    if conversational_overuse: enjoyment_issues.append("conversational_tone_overuse")\n\n    # Run140: composite reader outcome. This remains 0-API and soft-only: it does not trigger\n    # an extra Gemini call by itself. The generation prompt is responsible for achieving it.\n    reader_delight_good = (\n        opening_non_engineer_access == "GOOD"\n        and reader_proximity_moments >= 1\n        and not conversational_overuse\n        and article_specific_angle\n        and self_relevance\n        and (plain_language_bridge_present or not bridge_needed)\n    )\n    reader_delight = "GOOD" if reader_delight_good else "REVIEW"\n\n    # Reader-value budget:'''
if 'reader_delight_good = (' not in text:
    if issue_anchor not in text:
        raise SystemExit('Run140 anchor missing: reader delight composite')
    text = text.replace(issue_anchor, issue_repl, 1)

return_anchor = '        "reader_proximity": "GOOD" if reader_proximity_moments >= 1 and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),\n        "information_budget": information_budget,'
return_repl = '        "reader_proximity": "GOOD" if reader_proximity_moments >= 1 and not conversational_overuse else ("REVIEW_OVERUSE" if conversational_overuse else "REVIEW_MISSING"),\n        "reader_delight": reader_delight,\n        "information_budget": information_budget,'
if '"reader_delight": reader_delight' not in text:
    if return_anchor not in text:
        raise SystemExit('Run140 anchor missing: return')
    text = text.replace(return_anchor, return_repl, 1)

audit_anchor = '            f"- Reader Proximity: {reader.get(\'reader_proximity\')}",\n            f"- Reader Proximity Moment Count: {reader.get(\'reader_proximity_moment_count\')}",'
audit_repl = '            f"- Reader Proximity: {reader.get(\'reader_proximity\')}",\n            f"- Reader Delight: {reader.get(\'reader_delight\')}",\n            f"- Reader Proximity Moment Count: {reader.get(\'reader_proximity_moment_count\')}",'
if 'f"- Reader Delight:' not in text:
    if audit_anchor not in text:
        raise SystemExit('Run140 anchor missing: audit')
    text = text.replace(audit_anchor, audit_repl, 1)

path.write_text(text, encoding='utf-8')
