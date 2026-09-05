"""Deterministic editorial-naturalness diagnostics extracted from pipeline.py.

Run240 keeps these diagnostics provider-free, persistence-free and environment-free.
Runtime-specific inputs (display variants, peer memory, opening-excerpt behavior) are supplied
explicitly by pipeline.py so the extraction cannot silently freeze mutable Production state.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Callable


def classify_article_claims(parsed: dict) -> dict[str, int]:
    """Lightweight sentence-role counts used only as editorial observability."""
    article = parsed.get("note_draft", "") or ""
    action = parsed.get("action_text", "") or ""
    return {
        "fact": len(re.findall(r"(?:原資料|論文|著者|公式|公開|実験|データ|仕様|確認でき)", article)),
        "interpretation": len(re.findall(r"(?:と考えられる|と見える|私の推論|意味する|示唆)", article)),
        "observation": len(re.findall(r"(?:一方で|ただ|現時点では|注意|限界|課題|不明)", article)),
        "decision": len(re.findall(r"(?:私なら|試(?:す|したい)|検証(?:する|したい)|比較(?:する|したい)|見送(?:る|り)|待(?:つ|ち)|導入を急が|CI|回帰テスト|profil(?:ing|e)|プロファイリング|計測|ベンチマーク)", article + "\n" + action, re.I)),
    }


def find_fabricated_personal_experience(text: str) -> list[str]:
    """Allow editorial judgment while flagging unsupported first-person experience personas."""
    body = text or ""
    patterns = [
        r"現場で[^。！？\n]{0,40}(?:進める|担当する|運用する|働く)立場として",
        r"(?:私|筆者)(?:自身)?(?:は|が)?[^。！？\n]{0,50}(?:使ってみた|使っている|利用している|試した|導入した|運用した|経験した|遭遇した|体験した)",
        r"(?:私|筆者)(?:自身)?[^。！？\n]{0,35}(?:驚いた|ワクワクした|痛感した|実感した)",
        r"(?:^|[。！？\n])\s*日常(?:の|的な)[^。！？\n]{0,55}(?:感じます|実感します|経験しています|遭遇しています)",
    ]
    hits = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, re.I):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            if snippet:
                hits.append(snippet[:120])
    return list(dict.fromkeys(hits))[:4]


def ai_style_composite_signals(text: str, article_display_variants: list[dict]) -> dict:
    """High-precision zero-API detector for combinations of formulaic prose signals."""
    body = text or ""
    headings = [re.sub(r"\s+", " ", h).strip() for h in re.findall(r"^#{2,3}\s+(.+)$", body, re.MULTILINE)]
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)

    glue_phrases = ("ここで重要なのは", "注目すべきは", "ポイントは", "つまり", "言い換えると")
    glue_counts = {phrase: prose.count(phrase) for phrase in glue_phrases}
    glue_total = sum(glue_counts.values())
    repeated_glue = max(glue_counts.values(), default=0) >= 2

    point_ending_count = len(re.findall(r"という点(?:です|だ)[。！？]", prose))
    contrast_count = len(re.findall(r"[^。！？\n]{1,70}ではありません[。！？][^。！？\n]{1,70}(?:です|なのです)[。！？]", prose))
    enum_count = len(re.findall(r"(?:ひとつは|一つは|もうひとつは|もう一つは|理由は[二三23]つ|ポイントは[二三23]つ)", prose))

    template_headings = {
        variant[key]
        for variant in article_display_variants
        for key in ("intro", "conclusion", "why", "what", "key", "decision", "final")
    }
    template_heading_hits = sum(1 for h in headings if h in template_headings)
    generic_heading_hits = sum(
        1 for h in headings
        if re.fullmatch(r"(?:なぜ重要なのか[。？]?|ポイント[。？]?|要点[。？]?|まとめ[。？]?|結論[。？]?|何が違うのか[。？]?|何が新しいのか[。？]?)", h)
    )

    short_burst = False
    for para in re.split(r"\n\s*\n", prose):
        sentences = [s.strip() for s in re.split(r"(?<=[。！？])", para) if s.strip()]
        run = 0
        for sentence in sentences:
            visible = re.sub(r"[\s。！？]", "", sentence)
            run = run + 1 if 0 < len(visible) <= 18 else 0
            if run >= 3:
                short_burst = True
                break
        if short_burst:
            break

    section_lengths = []
    matches = list(re.finditer(r"^#{2,3}\s+.+$", body, re.MULTILINE))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        length = len(re.sub(r"\s+", "", body[start:end]))
        if length >= 80:
            section_lengths.append(length)
    uniform_sections = False
    if len(section_lengths) >= 5:
        mean = sum(section_lengths) / len(section_lengths)
        variance = sum((x - mean) ** 2 for x in section_lengths) / len(section_lengths)
        cv = (variance ** 0.5) / mean if mean else 1.0
        uniform_sections = cv < 0.18

    editorial_register_patterns = (
        r"注目すべき", r"興味深い", r"重要なのは", r"実務的な示唆", r"示唆的",
        r"明確な(?:ユースケース|選択肢|メリット|方向性)", r"きわめて(?:エレガント|重要|有効)",
        r"(?:非常に|きわめて)魅力的", r"(?:妥当|適切)な判断(?:と言えます|です)", r"と言えます",
        r"(?:ポイント|要点)を整理(?:します|すると)", r"第一の柱", r"(?:第一|第二|第三)段階(?:として|では)",
        r"(?:第一歩|鍵となる|一番の近道)", r"確かめてみてはいかがでしょうか",
    )
    editorial_register_hits = [pat for pat in editorial_register_patterns if re.search(pat, prose)]
    editorial_register_count = sum(len(re.findall(pat, prose)) for pat in editorial_register_patterns)
    visible_prose_chars = max(1, len(re.sub(r"\s+", "", prose)))
    editorial_register_per_1000 = editorial_register_count * 1000.0 / visible_prose_chars
    ordinal_framing_count = len(re.findall(r"(?:第一の柱|第一段階|第二段階|第三段階|第一に|第二に|第三に)", prose))

    evaluative_register_count = len(re.findall(
        r"(?:非常に|きわめて)魅力的|示唆的|実務的な示唆|明確な(?:ユースケース|選択肢|メリット|方向性)|"
        r"(?:妥当|適切)な判断(?:と言えます|です)|興味深い", prose
    ))
    explanatory_ending_count = len(re.findall(
        r"(?:と言えます|と言える|ことがわかります|ことが分かります|ことを示しています|ことを意味します)[。！？]", prose
    ))
    staged_framing_count = len(re.findall(
        r"(?:第一の柱|第一段階|第二段階|第三段階|第一に|第二に|第三に|第一歩|鍵となる|一番の近道)", prose
    ))
    invitational_close_count = len(re.findall(
        r"(?:してみてはいかがでしょうか|確かめてみてはいかがでしょうか|試してみてはいかがでしょうか)[。！？]?", prose
    ))
    editorial_habit_types = sum(bool(v) for v in (
        evaluative_register_count, explanatory_ending_count, staged_framing_count, invitational_close_count
    ))

    editorial_register_dense = (
        (editorial_register_count >= 5 and len(editorial_register_hits) >= 4 and editorial_register_per_1000 >= 1.0)
        or (editorial_register_count >= 4 and len(editorial_register_hits) >= 4 and editorial_habit_types >= 3)
    )
    editorial_register_companion = bool(
        ordinal_framing_count >= 2 or staged_framing_count >= 2 or point_ending_count >= 1 or repeated_glue
        or (evaluative_register_count >= 2 and invitational_close_count >= 1)
    )

    score = 0
    if glue_total >= 3: score += 2
    if repeated_glue: score += 1
    if point_ending_count >= 3: score += 2
    if contrast_count >= 2: score += 2
    if enum_count >= 2: score += 1
    if template_heading_hits >= 3: score += 3
    elif template_heading_hits >= 1: score += 1
    if generic_heading_hits >= 4: score += 2
    if short_burst: score += 1
    if uniform_sections: score += 1
    if editorial_register_dense and editorial_register_companion: score += 5

    return {
        "score": score,
        "high": score >= 5,
        "glue_total": glue_total,
        "repeated_glue": repeated_glue,
        "point_ending_count": point_ending_count,
        "contrast_count": contrast_count,
        "enum_count": enum_count,
        "template_heading_hits": template_heading_hits,
        "generic_heading_hits": generic_heading_hits,
        "short_burst": short_burst,
        "uniform_sections": uniform_sections,
        "editorial_register_count": editorial_register_count,
        "editorial_register_distinct": len(editorial_register_hits),
        "editorial_register_per_1000": editorial_register_per_1000,
        "editorial_register_dense": editorial_register_dense,
        "editorial_register_companion": editorial_register_companion,
        "ordinal_framing_count": ordinal_framing_count,
        "evaluative_register_count": evaluative_register_count,
        "explanatory_ending_count": explanatory_ending_count,
        "staged_framing_count": staged_framing_count,
        "invitational_close_count": invitational_close_count,
        "editorial_habit_types": editorial_habit_types,
    }


def sentence_shingles(value: str, width: int = 5) -> set[str]:
    compact = re.sub(r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+", " ", value or "")
    compact = re.sub(r"[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+", "", compact)
    if len(compact) < width:
        return set()
    return {compact[i:i + width] for i in range(len(compact) - width + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def human_editorial_depth_signals(text: str) -> dict:
    """Run121 zero-API signals for over-explaining and mechanically explicit prose."""
    body = text or ""
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    sentences = [x.strip() for x in re.split(r"(?<=[。！？!?])", prose) if len(re.sub(r"\s+", "", x)) >= 28]
    near_duplicate_pairs = 0
    for i, left in enumerate(sentences):
        a = sentence_shingles(left)
        if len(a) < 8:
            continue
        for right in sentences[i + 1:i + 7]:
            b = sentence_shingles(right)
            if len(b) >= 8 and jaccard(a, b) >= 0.66:
                near_duplicate_pairs += 1
                break

    transitions = ("一方で", "ただし", "そのため", "つまり", "また", "さらに", "そこで", "とはいえ", "なお", "逆に")
    transition_counts = {t: len(re.findall(rf"(?:^|[。！？!?\n])\s*{re.escape(t)}", prose)) for t in transitions}
    transition_total = sum(transition_counts.values())
    repeated_transition = max(transition_counts.values(), default=0) >= 3
    explanatory_closer_count = len(re.findall(r"(?:と言えます|といえます|と考えられます|ということです|ことになります|わけです)[。！？]", prose))

    score = 0
    if near_duplicate_pairs >= 2: score += 3
    elif near_duplicate_pairs == 1: score += 1
    if transition_total >= 8: score += 2
    elif transition_total >= 6: score += 1
    if repeated_transition: score += 1
    if explanatory_closer_count >= 3: score += 2
    return {
        "score": score,
        "high": score >= 4,
        "near_duplicate_pairs": near_duplicate_pairs,
        "transition_total": transition_total,
        "repeated_transition": repeated_transition,
        "explanatory_closer_count": explanatory_closer_count,
    }


def style_sequence(article: str) -> tuple[str, ...]:
    prose = re.sub(r"^#{1,6}\s+.*$", "", article or "", flags=re.MULTILINE)
    result: list[str] = []
    transition_map = (("一方で", "T_CONTRAST"), ("ただし", "T_CAVEAT"), ("そのため", "T_CAUSE"),
                      ("つまり", "T_SUMMARY"), ("また", "T_ADD"), ("さらに", "T_ADD"),
                      ("そこで", "T_ACTION"), ("とはいえ", "T_CAVEAT"))
    for raw in re.split(r"(?<=[。！？!?])", prose):
        sentence = re.sub(r"\s+", " ", raw).strip()
        visible = re.sub(r"[\s。！？!?]", "", sentence)
        if len(visible) < 8:
            continue
        length = "S" if len(visible) <= 28 else "M" if len(visible) <= 58 else "L" if len(visible) <= 95 else "XL"
        trans = "T_NONE"
        for prefix, code in transition_map:
            if sentence.startswith(prefix):
                trans = code
                break
        if re.search(r"(?:たい|妥当|価値がある|見送り|急がない)[。！？!?]?$", sentence): end = "E_DECISION"
        elif re.search(r"(?:可能性があります|考えられます|かもしれません)[。！？!?]?$", sentence): end = "E_HEDGE"
        elif re.search(r"(?:ということです|わけです|と言えます|といえます)[。！？!?]?$", sentence): end = "E_EXPLAIN"
        elif re.search(r"ます[。！？!?]?$", sentence): end = "E_MASU"
        elif re.search(r"です[。！？!?]?$", sentence): end = "E_DESU"
        else: end = "E_OTHER"
        result.extend((length, trans, end))
        if len(result) >= 45:
            break
    return tuple(result)


def rhetorical_template_phrases(article: str) -> set[str]:
    """Weak signature for entertainment-template reuse across articles."""
    candidates = (
        "実は", "少し考えてみましょう", "ここがおもしろいところです",
        "また3文字の専門用語か", "恋愛に例えるなら", "猫で考えると",
        "天才だけど", "に例えると", "例えるなら",
    )
    text = article or ""
    return {phrase for phrase in candidates if phrase in text}


def cross_article_naturalness_signals(
    article: str,
    peer_rows: list[dict] | None,
    opening_excerpt: Callable[[str, int], str],
) -> dict:
    """Detect run-level template fingerprints without semantic/model comparison."""
    seq = style_sequence(article)
    headings = [re.sub(r"[\s。、！？!?]", "", h) for h in re.findall(r"^#{2,3}\s+(.+)$", article or "", re.MULTILINE)]
    heading_count = len(headings)
    intro = opening_excerpt(article, 520)
    intro_shingles = sentence_shingles(intro, 5)
    rhetorical = rhetorical_template_phrases(article)
    best = {"score": 0, "peer": "", "sequence_similarity": 0.0, "opening_similarity": 0.0, "heading_count_match": False, "shared_rhetorical_phrases": []}
    for peer in peer_rows or []:
        other_seq = tuple(peer.get("sequence") or ())
        shared_rhetorical = sorted(rhetorical & set(peer.get("rhetorical_phrases") or ()))
        if len(seq) < 18 or len(other_seq) < 18:
            if len(shared_rhetorical) >= 2 and not best.get("shared_rhetorical_phrases"):
                best = {"score": 1, "peer": str(peer.get("name") or ""), "sequence_similarity": 0.0,
                        "opening_similarity": 0.0, "heading_count_match": False,
                        "shared_rhetorical_phrases": shared_rhetorical}
            continue
        sequence_similarity = SequenceMatcher(None, seq, other_seq, autojunk=False).ratio()
        opening_similarity = jaccard(intro_shingles, set(peer.get("opening_shingles") or ()))
        heading_match = heading_count >= 3 and heading_count == int(peer.get("heading_count") or 0)
        score = 0
        if sequence_similarity >= 0.88: score += 3
        elif sequence_similarity >= 0.82: score += 2
        if opening_similarity >= 0.58: score += 2
        elif opening_similarity >= 0.48: score += 1
        if heading_match: score += 1
        if len(shared_rhetorical) >= 2: score += 1
        if score > best["score"]:
            best = {"score": score, "peer": str(peer.get("name") or ""), "sequence_similarity": sequence_similarity,
                    "opening_similarity": opening_similarity, "heading_count_match": heading_match,
                    "shared_rhetorical_phrases": shared_rhetorical}
    best["high"] = best["score"] >= 4
    return best
