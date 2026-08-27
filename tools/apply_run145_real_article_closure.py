from pathlib import Path

p = Path('pipeline.py')
s = p.read_text(encoding='utf-8')
original = s

# 1) Real-article security overclaim closure: absolute host/PC safety claims are hard fact defects.
anchor = '''    # 「保証」単独もHigh Risk Claimとして検査する。ただし公式の保証があれば許可する。\n'''
insert = '''    # Run145: 実記事で確認したsandbox/securityの絶対保証を個別に閉じる。\n    # 「影響を狭めやすい」のような限定表現は対象外。何をしても影響なし／被害を特定範囲に\n    # 抑え込める、といった保証相当の断定だけをHard Fact defectとして扱う。\n    run145_security_overclaims = (\n        (r"(?:AI|エージェント|サンドボックス|sandbox)[^。！？\\n]{0,90}(?:どんな|いかなる|何をしても)[^。！？\\n]{0,90}(?:PC|ホスト|端末|本体)[^。！？\\n]{0,50}(?:影響が及びません|影響は及びません|影響しません)", "unsupported absolute isolation"),\n        (r"(?:被害|影響)(?:の)?範囲を[^。！？\\n]{0,80}(?:だけ|のみ|内|範囲内)[^。！？\\n]{0,50}(?:に)?(?:抑え込める|封じ込められる|限定できる)", "unsupported containment guarantee"),\n    )\n    for pattern, label in run145_security_overclaims:\n        for m in re.finditer(pattern, text, re.I):\n            if not _claim_is_negated(text, m.start(), m.end()):\n                failures.append(f"{label}: {m.group(0)}")\n                break\n\n'''
if anchor not in s:
    raise SystemExit('Run145 hype anchor not found')
s = s.replace(anchor, insert + anchor, 1)

# 2) 0-API deterministic repair for the real malformed ordinal observed in MCP output.
struct_anchor = '''def _apply_deterministic_structure_polish(parsed: dict) -> tuple[dict, list[str]]:\n'''
helper = '''def _repair_malformed_reader_numbering(article: str) -> tuple[str, list[str]]:\n    """Repair only unmistakable line-leading ordinal collisions without changing facts.\n\n    Real regression produced e.g. ``2.2026年〜``.  This is typography, not content, so repair it\n    locally with zero Gemini calls.  Mid-sentence decimals/versions are intentionally untouched.\n    """\n    body = article or ""\n    repaired, count = re.subn(r"(?m)^(\\s*\\d{1,2})\\.(?=20\\d{2}年)", r"\\1. ", body)\n    return repaired, ([f"repair_malformed_ordinal_year:{count}"] if count else [])\n\n\n'''
if struct_anchor not in s:
    raise SystemExit('Run145 structure anchor not found')
s = s.replace(struct_anchor, helper + struct_anchor, 1)

old_struct = '''    article, headings = _promote_plaintext_section_titles(str(polished.get("note_draft") or ""))\n    if headings:\n        polished["note_draft"] = article\n    return polished, [f"promote_plaintext_heading:{h}" for h in headings]\n'''
new_struct = '''    article, headings = _promote_plaintext_section_titles(str(polished.get("note_draft") or ""))\n    article, numbering_changes = _repair_malformed_reader_numbering(article)\n    if headings or numbering_changes:\n        polished["note_draft"] = article\n    return polished, [f"promote_plaintext_heading:{h}" for h in headings] + numbering_changes\n'''
if old_struct not in s:
    raise SystemExit('Run145 structure body anchor not found')
s = s.replace(old_struct, new_struct, 1)

# 3) Prompt: preserve article-specific human opening even for roadmaps/protocols; forbid safety guarantees.
prompt_anchor = '''・別の記事でも使える汎用的な導入・判断フレーズへ逃げず、この一次情報だから成立する入口と情報順序を選ぶ。\n'''
prompt_insert = '''・Roadmap、protocol、SDK、仕様変更のような抽象テーマでも、定義や項目列挙から始めない。読者が実際に困る場面、従来の前提が崩れる瞬間、または「なぜ今これが話題なのか」という記事固有の違和感から入り、そこから技術の核心へ進む。架空の体験談は作らない。\n・Security / Sandbox / Isolationでは「何をしてもPCへ影響しない」「被害をこの範囲だけに抑え込める」「安全が担保される」のような保証相当の断定をしない。一次情報が示す隔離機構と、残る条件・制約を分けて書く。\n'''
if prompt_anchor not in s:
    raise SystemExit('Run145 editorial prompt anchor not found')
s = s.replace(prompt_anchor, prompt_anchor + prompt_insert, 1)

article_anchor = '''タイトル直後は、読者が「何の話か」「なぜ自分に関係するか」をつかめる自然なリードから始める。\n'''
article_insert = '''Roadmapやprotocolの話でも、冒頭を「〜とは」「主な変更点は」「今回のロードマップでは」の説明開始に固定しない。まず読者が引っかかる変化・困りごと・意外性を1つ置き、専門用語は理解が必要になった時点で名前を付ける。\n'''
if article_anchor not in s:
    raise SystemExit('Run145 article lead anchor not found')
s = s.replace(article_anchor, article_anchor + article_insert, 1)

if s == original:
    raise SystemExit('Run145 made no changes')
p.write_text(s, encoding='utf-8')
print('Run145 patch applied')
